# backend/app/routes/auth.py
from datetime import timedelta
import os

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import obtener_usuario_por_email
from app.auth import (
    verificar_password,
    crear_token_acceso,   # genera JWT con expiración configurable
    decodificar_token,    # valida/decodifica JWT
)

router = APIRouter(prefix="/auth", tags=["auth"])
legacy = APIRouter(tags=["auth"])

# ============= Config cookie de refresh =============
COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"  # en local: false
COOKIE_HTTPONLY = True
COOKIE_SAMESITE = "none"  # front/back en dominios distintos (HTTPS)
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

# ================= Helpers =================
class LoginJSON(BaseModel):
    email: str
    password: str

def _issue_access(email: str) -> str:
    # access corto (usa tu crear_token_acceso; por defecto 60 min)
    return crear_token_acceso({"sub": email, "type": "access"})

def _issue_refresh(email: str) -> str:
    # refresh largo (30 días por defecto)
    return crear_token_acceso({"sub": email, "type": "refresh"},
                              expires_delta=timedelta(days=REFRESH_DAYS))

def _token_response(email: str, response: Response):
    access = _issue_access(email)
    refresh = _issue_refresh(email)
    _set_refresh_cookie(response, refresh)
    return {"access_token": access, "token_type": "bearer", "user": {"email": email}}

def _login(db: Session, username_or_email: str, password: str, response: Response):
    user = obtener_usuario_por_email(db, username_or_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    hashed = getattr(user, "hashed_password", None) or getattr(user, "password_hash", None) or getattr(user, "password", None)
    if not hashed or not verificar_password(password, hashed):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return _token_response(user.email, response)

# ================= Endpoints =================
@router.post("/login", summary="Login (form-urlencoded: username, password)")
def login_form(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@router.post("/token", summary="Alias de /auth/login")
def token_form(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@router.post("/login-json", summary="Login JSON {email,password}")
def login_json(response: Response, payload: LoginJSON, db: Session = Depends(get_db)):
    return _login(db, payload.email, payload.password, response)

@router.post("/refresh", summary="Emite nuevo access usando cookie httpOnly refresh_token (rota refresh)")
def refresh(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    data = decodificar_token(token)
    if not data or data.get("type") != "refresh" or not data.get("sub"):
        raise HTTPException(status_code=401, detail="Refresh inválido")
    email = data["sub"]
    new_access = _issue_access(email)
    new_refresh = _issue_refresh(email)  # rotación
    _set_refresh_cookie(response, new_refresh)
    return {"access_token": new_access, "token_type": "bearer"}

@router.post("/logout", summary="Borra cookie refresh_token")
def logout(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME,
        path=COOKIE_PATH,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
    )
    return {"ok": True}

# ===== Aliases legacy (/api/login y /api/login/token) =====
@legacy.post("/login")
def legacy_login(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@legacy.post("/login/token")
def legacy_login_token(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)
