from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os

from app.database import get_db
from app.crud import obtener_usuario_por_email
from app.auth import verificar_password, crear_token_acceso  # tu core (ACCESS)
from app.auth_tokens import create_refresh_token, decode_refresh  # REFRESH JWT

router = APIRouter(prefix="/auth", tags=["auth"])   # /api/auth/...
legacy = APIRouter(tags=["auth"])                   # /api/...

# ======= Config de cookie =======
COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_HTTPONLY = True
COOKIE_SAMESITE = "none"
REFRESH_MAX_AGE = 60 * 60 * 24 * 30  # 30 días

def _set_refresh_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=REFRESH_MAX_AGE,
        path=COOKIE_PATH,
        secure=COOKIE_SECURE,
        httponly=COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE,
    )

class LoginJSON(BaseModel):
    email: str
    password: str

def _extract_role(user) -> str:
    # Soporta modelos con 'role' o 'rol'
    return getattr(user, "role", None) or getattr(user, "rol", None) or "employee"

def _token_response(user, response: Response):
    """
    Devuelve access_token en body y setea refresh_token en cookie httpOnly.
    AHORA el access_token incluye 'role' y la respuesta siempre trae 'role' correcto.
    """
    role = _extract_role(user)
    claims = {"sub": user.email, "role": role}
    access_token = crear_token_acceso(claims)                     # access con role
    refresh_token = create_refresh_token(subject=user.email)      # refresh (cookie)
    _set_refresh_cookie(response, refresh_token)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"email": user.email, "role": role},
    }

def _login(db: Session, username_or_email: str, password: str, response: Response):
    user = obtener_usuario_por_email(db, username_or_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    hashed = getattr(user, "hashed_password", None) or getattr(user, "password_hash", None) or getattr(user, "password", None)
    if not hashed or not verificar_password(password, hashed):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return _token_response(user, response)

# ====== Endpoints de login ======
@router.post("/login", summary="Login (x-www-form-urlencoded: username, password)")
def login_form(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@router.post("/token", summary="Alias de /auth/login")
def token_form(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@router.post("/login-json", summary="Login JSON {email,password}")
def login_json(response: Response, payload: LoginJSON, db: Session = Depends(get_db)):
    return _login(db, payload.email, payload.password, response)

# ====== Refresh y logout ======
@router.post("/refresh", summary="Usa cookie httpOnly refresh_token para emitir nuevo access con role")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        data = decode_refresh(token)      # valida refresh (firma/exp/type)
        if data.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido")
        subject = data.get("sub")
        if not subject:
            raise HTTPException(status_code=401, detail="Token inválido")
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh inválido")

    # Cargar usuario para saber su role actual
    user = obtener_usuario_por_email(db, subject)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    role = _extract_role(user)
    new_access = crear_token_acceso({"sub": subject, "role": role})
    new_refresh = create_refresh_token(subject=subject)
    _set_refresh_cookie(response, new_refresh)
    return {"access_token": new_access, "token_type": "bearer", "user": {"email": subject, "role": role}}

@router.post("/logout", summary="Borra cookie refresh_token")
def logout(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME,
        path=COOKIE_PATH,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
    )
    return {"ok": True}

# ===== Aliases legacy =====
@legacy.post("/login", summary="LEGACY: /api/login -> /api/auth/login")
def legacy_login(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@legacy.post("/login/token", summary="LEGACY: /api/login/token -> /api/auth/login")
def legacy_login_token(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)
