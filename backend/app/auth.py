import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import obtener_usuario_por_email

load_dotenv()

# ====== JWT ======
SECRET_KEY = os.getenv("SECRET_KEY", "clave-secreta-super-segura")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_MIN", "60"))

# ====== Password hashing ======
# Acepta bcrypt y algunos esquemas comunes (por compatibilidad)
pwd_context = CryptContext(
    schemes=["bcrypt", "pbkdf2_sha256", "sha256_crypt"],
    deprecated="auto",
)

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verificación robusta:
    - strip() para eliminar espacios/nueva línea que a veces se cuelan desde la UI de la BD.
    - normaliza prefijo $2y$ -> $2b$ (histórico de bcrypt).
    - tolera copias con texto adicional escogiendo el primer token que parezca hash bcrypt.
    """
    try:
        h = (hashed_password or "").strip()
        if h.startswith("$2y$"):
            h = "$2b$" + h[4:]
        if len(h) > 60 and "$2b$" in h:
            for token in h.split():
                if token.startswith("$2b$") and len(token) >= 60:
                    h = token[:60]
                    break
        return pwd_context.verify(plain_password, h)
    except Exception as e:
        print("[AUTH_VERIFY_ERROR]", repr(e))
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

# ====== Auth dependency (para rutas protegidas) ======
auth_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    payload = decodificar_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")
    email = (payload.get("sub") or "").strip()
    user = obtener_usuario_por_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user

