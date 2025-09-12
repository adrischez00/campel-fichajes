from datetime import timedelta
import os
import traceback

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import obtener_usuario_por_email
from app.auth import (
    verificar_password,
    crear_token_acceso,
    decodificar_token,
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
DEBUG_AUTH = os.getenv("DEBUG_AUTH", "0") not in ("0", "false", "False", "")

def _dbg(*args):
    if DEBUG_AUTH:
        print("[AUTH]", *args)

def _set_refresh_cookie(resp: Response, token: str):
    # set_cookie NUNCA debe explotar; rodeamos por si acaso (evita 500)
    try:
        resp.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=60 * 60 * 24 * REFRESH_DAYS,
            path=COOKIE_PATH,
            secure=COOKIE_SECURE,
            httponly=COOKIE_HTTPONLY,
            samesite=COOKIE_SAMESITE,
        )
    except Exception as e:
        _dbg("set_cookie error:", repr(e))

# ================= Helpers =================
class LoginJSON(BaseModel):
    email: str
    password: str

def _issue_access(email: str) -> str:
    return crear_token_acceso({"sub": email, "type": "access"})

def _issue_refresh(email: str) -> str:
    return crear_token_acceso({"sub": email, "type": "refresh"},
                              expires_delta=timedelta(days=REFRESH_DAYS))

def _token_response(user, response: Response):
    access = _issue_access(user.email)
    refresh = _issue_refresh(user.email)
    _set_refresh_cookie(response, refresh)
    return {
        "access_token": access,
        "token_type": "bearer",
        "user": {"email": user.email, "role": getattr(user, "role", None)},
    }

def _safe_verify(plain: str, hashed: str) -> bool:
    try:
        return verificar_password(plain, hashed)
    except Exception as e:
        _dbg("verify error:", repr(e))
        return False

def _login_core(db: Session, username_or_email: str, password: str, response: Response):
    _dbg("login", username_or_email)
    user = obtener_usuario_por_email(db, username_or_email)
    if not user:
        _dbg("user not found")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    hashed = (
        getattr(user, "hashed_password", None)
        or getattr(user, "password_hash", None)
        or getattr(user, "password", None)
    )
    if not hashed:
        _dbg("no hashed field in user")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    if not _safe_verify(password, hashed):
        _dbg("password mismatch")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    return _token_response(user, response)

# Importante: NUNCA devolver 500 en login; si algo raro pasa, devolver 401 con detalle neutro.
def _login(db: Session, username_or_email: str, password: str, response: Response):
    try:
        return _login_core(db, username_or_email, password, response)
    except HTTPException:
        raise
    except Exception as e:
        _dbg("unexpected:", repr(e))
        if DEBUG_AUTH:
            traceback.print_exc()
        # degradamos a 401 para no romper el front
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

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
    try:
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            _dbg("no refresh cookie")
            raise HTTPException(status_code=401, detail="No refresh token")
        data = decodificar_token(token)
        if not data or data.get("type") != "refresh" or not data.get("sub"):
            _dbg("invalid refresh payload", data)
            raise HTTPException(status_code=401, detail="Refresh inválido")
        email = data["sub"]
        new_access = _issue_access(email)
        new_refresh = _issue_refresh(email)
        _set_refresh_cookie(response, new_refresh)
        return {"access_token": new_access, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        _dbg("refresh unexpected:", repr(e))
        if DEBUG_AUTH:
            traceback.print_exc()
        raise HTTPException(status_code=401, detail="Refresh inválido")

@router.post("/logout", summary="Borra cookie refresh_token")
def logout(response: Response):
    try:
        response.delete_cookie(
            key=COOKIE_NAME,
            path=COOKIE_PATH,
            samesite=COOKIE_SAMESITE,
            secure=COOKIE_SECURE,
        )
    except Exception as e:
        _dbg("delete_cookie error:", repr(e))
    return {"ok": True}

# Aliases legacy
@legacy.post("/login")
def legacy_login(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@legacy.post("/login/token")
def legacy_login_token(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)
