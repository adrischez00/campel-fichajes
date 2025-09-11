from datetime import timedelta
import os

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Query
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import obtener_usuario_por_email
from app.auth import (
    verificar_password,
    crear_token_acceso,
    decodificar_token,
    pwd_context,  # solo para debug info
)

router = APIRouter(prefix="/auth", tags=["auth"])
legacy = APIRouter(tags=["auth"])

DEBUG_AUTH = os.getenv("DEBUG_AUTH", "0") not in ("0", "false", "False")

# ============= Config cookie de refresh =============
COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"  # en local: false
COOKIE_HTTPONLY = True
COOKIE_SAMESITE = "none"  # front/back distintos (HTTPS)
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
        return verificar_password(plain, (hashed or ""))
    except Exception:
        return False

def _login(db: Session, username_or_email: str, password: str, response: Response):
    user = obtener_usuario_por_email(db, username_or_email)
    if not user:
        if DEBUG_AUTH:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"msg": "Credenciales inválidas", "user_found": False}
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    hashed = (
        getattr(user, "hashed_password", None)
        or getattr(user, "password_hash", None)
        or getattr(user, "password", None)
    )

    ok = bool(hashed) and _safe_verify(password, hashed)
    if not ok:
        if DEBUG_AUTH:
            # devolvemos LONGITUD y prefijo del hash para diagnosticar, no el hash completo
            detail = {
                "msg": "Credenciales inválidas",
                "user_found": True,
                "hash_len": len(hashed) if hashed else None,
                "hash_prefix": (hashed[:7] if hashed else None),
                "schemes": list(pwd_context.schemes()),
            }
            raise HTTPException(status_code=401, detail=detail)
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    return _token_response(user, response)

# ================= Endpoints =================
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

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME,
        path=COOKIE_PATH,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
    )
    return {"ok": True}

# ===== Aliases legacy =====
@legacy.post("/login")
def legacy_login(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@legacy.post("/login/token")
def legacy_login_token(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

# ===== Debug opcional (quítalos cuando termines) =====
@router.get("/debug-user")
def debug_user(email: str = Query(..., min_length=3), db: Session = Depends(get_db)):
    u = obtener_usuario_por_email(db, email)
    if not u:
        return {"found": False}
    h = getattr(u, "hashed_password", None) or getattr(u, "password_hash", None) or getattr(u, "password", None)
    return {
        "found": True,
        "email": u.email,
        "hash_len": len(h) if h else None,
        "hash_prefix": (h[:7] if h else None),
    }

class _VerifyBody(BaseModel):
    password: str
    hashed: str

@router.post("/debug-verify")
def debug_verify(b: _VerifyBody):
    try:
        ok = verificar_password(b.password, b.hashed)
        return {"ok": ok}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

