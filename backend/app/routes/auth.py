from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import obtener_usuario_por_email
from app.auth import verificar_password, crear_token_acceso

router = APIRouter(prefix="/auth", tags=["auth"])
legacy = APIRouter(tags=["auth"])

class LoginJSON(BaseModel):
    email: str
    password: str

def _login(db: Session, username_or_email: str, password: str):
    user = obtener_usuario_por_email(db, (username_or_email or "").strip())
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    hashed = (
        getattr(user, "hashed_password", None)
        or getattr(user, "password_hash", None)
        or getattr(user, "password", None)
    )
    ok = False
    try:
        ok = bool(hashed) and verificar_password(password or "", hashed)
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    access = crear_token_acceso({"sub": user.email, "type": "access"})
    return {
        "access_token": access,
        "token_type": "bearer",
        "user": {"email": user.email, "role": getattr(user, "role", None)},
    }

@router.post("/login", summary="Login (x-www-form-urlencoded: username,password)")
def login_form(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password)

@router.post("/token", summary="Alias de /auth/login")
def token_form(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password)

@router.post("/login-json", summary="Login JSON {email,password}")
def login_json(response: Response, payload: LoginJSON, db: Session = Depends(get_db)):
    return _login(db, payload.email, payload.password)

# Aliases legacy (por compatibilidad)
@legacy.post("/login")
def legacy_login(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password)

@legacy.post("/login/token")
def legacy_login_token(response: Response, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _login(db, form.username, form.password)
