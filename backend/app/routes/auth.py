# backend/app/routes/auth.py
import os
import traceback
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import obtener_usuario_por_email
from app.auth import verificar_password, crear_token_acceso, decodificar_token

router = APIRouter(prefix="/auth", tags=["auth"])
legacy = APIRouter(tags=["auth"])

def _dbg(msg: str):
    print(f"[AUTHDEBUG] {msg}")

# ============= cookie refresh =============
COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"  # en local: false
COOKIE_HTTPONLY = True
COOKIE_SAMESITE = "none"
REFRESH_DAYS = int(os.getenv("REFRESH_DAYS", "30"))

def _set_refresh_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=60 * 60 * 24 * REFRESH_DAYS,
        path=COOKIE_PATH,
        secure=COOKIE_SECURE,
        httponly=COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE,
    )

class LoginJSON(BaseModel):
    email: str
    password: str

def _issue_access(email: str, role: str | None) -> str:
    # access con role embebido
    return crear_token_acceso({"sub": email, "role": role, "type": "access"})

def _issue_refresh(email: str) -> str:
    # refresh largo (no necesitamos meter role aquí; lo cargamos de DB en /refresh)
    return crear_token_acceso({"sub": email, "type": "refresh"},
                              expires_delta=timedelta(days=REFRESH_DAYS))

def _token_response(user, response: Response):
    role = getattr(user, "role", None)
    access = _issue_access(user.email, role)
    refresh = _issue_refresh(user.email)
    _set_refresh_cookie(response, refresh)
    return {
        "access_token": access,
        "token_type": "bearer",
        "user": {"email": user.email, "role": role},
    }

def _login(db: Session, username_or_email: str, password: str, response: Response):
    try:
        email_in = (username_or_email or "").strip()
        _dbg(f"login attempt email='{email_in}'")

        user = obtener_usuario_por_email(db, email_in)
        _dbg(f"user_found={bool(user)}")

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

        hashed = (
            getattr(user, "hashed_password", None)
            or getattr(user, "password_hash", None)
            or getattr(user, "password", None)
        )
        _dbg(f"user.hash len={len(hashed or '')} pref='{(hashed or '')[:7]}'")

        ok = verificar_password(password, hashed or "")
        _dbg(f"password_ok={ok}")

        if not ok:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

        return _token_response(user, response)

    except HTTPException:
        raise
    except Exception as e:
        _dbg(f"_login unexpected: {repr(e)}")
        _dbg(traceback.format_exc())
        # No filtramos a cliente: 401 genérico
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

# ===== endpoints =====
@router.post("/login")
def login_form(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@router.post("/token")
def token_form(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@router.post("/login-json")
def login_json(response: Response, payload: LoginJSON, db: Session = Depends(get_db)):
    return _login(db, payload.email, payload.password, response)

@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    data = decodificar_token(token)
    if not data or data.get("type") != "refresh" or not data.get("sub"):
        raise HTTPException(status_code=401, detail="Refresh inválido")

    email = data["sub"]
    # Cargamos user para obtener el role actual
    user = obtener_usuario_por_email(db, email)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    new_access = _issue_access(user.email, getattr(user, "role", None))
    new_refresh = _issue_refresh(user.email)  # rotación
    _set_refresh_cookie(response, new_refresh)
    return {
        "access_token": new_access,
        "token_type": "bearer",
        "user": {"email": user.email, "role": getattr(user, "role", None)}
    }

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME,
        path=COOKIE_PATH,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
    )
    return {"ok": True}

# Aliases legacy
@legacy.post("/login")
def legacy_login(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@legacy.post("/login/token")
def legacy_login_token(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)
