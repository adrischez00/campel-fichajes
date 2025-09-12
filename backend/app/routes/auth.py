import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import obtener_usuario_por_email
from app.auth import verificar_password, crear_token_acceso, decodificar_token

router = APIRouter(prefix="/auth", tags=["auth"])
legacy = APIRouter(tags=["auth"])

# Cookies de refresh
COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
COOKIE_HTTPONLY = True
COOKIE_SAMESITE = "none"  # dominios distintos
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

def _login(db: Session, username_or_email: str, password: str, response: Response):
    user = obtener_usuario_por_email(db, username_or_email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    hashed = getattr(user, "hashed_password", None) or getattr(user, "password_hash", None) or getattr(user, "password", None)
    if not hashed or not verificar_password(password, hashed):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    return _token_response(user, response)

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
    new_refresh = _issue_refresh(email)
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

# Aliases legacy
@legacy.post("/login")
def legacy_login(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)

@legacy.post("/login/token")
def legacy_login_token(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password, response)
