import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt as bcrypt_hash
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import obtener_usuario_por_email

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "clave-secreta-super-segura")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_MIN", "60"))

# acepta varios esquemas de hash (bcrypt + comunes)
pwd_context = CryptContext(
    schemes=["bcrypt", "pbkdf2_sha256", "sha256_crypt"],
    deprecated="auto",
)

auth_scheme = HTTPBearer()

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )
    return user

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica robusto:
    1) CryptContext (maneja múltiples esquemas).
    2) Fallback: verificador bcrypt directo (soporta $2a$, $2b$, $2y$).
    Nunca lanza excepción: False si no coincide / hash inválido.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        if pwd_context.verify(plain_password, hashed_password):
            return True
    except Exception:
        pass
    # Fallback específico bcrypt (por si el hash es $2a$/legacy)
    try:
        if hashed_password.startswith("$2"):
            return bcrypt_hash.verify(plain_password, hashed_password)
    except Exception:
        pass
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
    except JWTError:
        return None
