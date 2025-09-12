import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
import bcrypt  # <- fallback directo

from sqlalchemy.orm import Session
from app.database import get_db
from app.crud import obtener_usuario_por_email

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "clave-secreta-super-segura")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_MIN", "60"))

# Acepta distintos hashes comunes
pwd_context = CryptContext(
    schemes=["bcrypt", "pbkdf2_sha256", "sha256_crypt"],
    deprecated="auto",
)

auth_scheme = HTTPBearer()

DEBUG_AUTH = os.getenv("DEBUG_AUTH", "0") not in ("0", "false", "False")

def _dbg(msg: str):
    if DEBUG_AUTH:
        print(f"[AUTH] {msg}")

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    payload = decodificar_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    email = (payload.get("sub") or "").strip()
    user = obtener_usuario_por_email(db, email)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


def verificar_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica primero con passlib y, si falla o lanza excepción,
    intenta un fallback con bcrypt.checkpw (soporta $2a$ / $2b$ / $2y$).
    """
    try:
        ok = pwd_context.verify(plain_password, hashed_password)
        _dbg(f"passlib.verify -> {ok}")
        if ok:
            return True
    except Exception as e:
        _dbg(f"passlib.verify EXC: {e}")

    # Fallback con bcrypt nativo
    try:
        ok2 = bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
        _dbg(f"bcrypt.checkpw -> {ok2}")
        return ok2
    except Exception as e:
        _dbg(f"bcrypt.checkpw EXC: {e}")
        return False


def hashear_password(password: str) -> str:
    return pwd_context.hash(password)


def crear_token_acceso(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decodificar_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        _dbg(f"decode EXC: {e}")
        return None
