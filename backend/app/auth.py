import os
import traceback
from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt as _bcrypt
from passlib.hash import pbkdf2_sha256 as _pbkdf2
from passlib.hash import sha256_crypt as _sha256
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import obtener_usuario_por_email

# ========= JWT =========
SECRET_KEY = os.getenv("SECRET_KEY", "clave-secreta-super-segura")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_MIN", "60"))

# ========= Password hashing (admite varios) =========
pwd_context = CryptContext(
    schemes=["bcrypt", "pbkdf2_sha256", "sha256_crypt"],
    deprecated="auto",
)

auth_scheme = HTTPBearer()

def _dbg(msg: str):
    # Debug SIEMPRE activo
    print(f"[AUTHDEBUG] {msg}")

def _guess_scheme(h: str) -> str:
    if not h:
        return "empty"
    if h.startswith(("$2a$", "$2b$", "$2y$")):
        return "bcrypt"
    if h.startswith("$pbkdf2-sha256$"):
        return "pbkdf2_sha256"
    if h.startswith("$5$") or h.startswith("$6$") or h.startswith("$sha256$"):
        return "sha256_crypt"
    return "unknown"

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    """Verificación robusta con logs detallados."""
    h = (hashed_password or "").strip()
    _dbg(f"verify: scheme={_guess_scheme(h)} len={len(h)} pref='{h[:7]}'")

    # 1) Intento estándar con passlib Context
    try:
        ok = pwd_context.verify(plain_password, h)
        _dbg(f"verify: passlib.verify -> {ok}")
        if ok:
            return True
    except Exception as e:
        _dbg(f"verify: passlib.verify raised {repr(e)}")
        _dbg(traceback.format_exc())

    # 2) Fallbacks por esquema explícito
    try:
        if h.startswith(("$2a$", "$2b$", "$2y$")):
            ok = _bcrypt.verify(plain_password, h)
            _dbg(f"verify: bcrypt fallback -> {ok}")
            if ok:
                return True
        if h.startswith("$pbkdf2-sha256$"):
            ok = _pbkdf2.verify(plain_password, h)
            _dbg(f"verify: pbkdf2 fallback -> {ok}")
            if ok:
                return True
        if h.startswith("$5$") or h.startswith("$6$") or h.startswith("$sha256$"):
            ok = _sha256.verify(plain_password, h)
            _dbg(f"verify: sha256_crypt fallback -> {ok}")
            if ok:
                return True
    except Exception as e:
        _dbg(f"verify: explicit fallback raised {repr(e)}")
        _dbg(traceback.format_exc())

    # 3) Señalización si parece texto plano en BD
    if plain_password == h and h:
        _dbg("verify: WARNING -> la contraseña almacenada parece texto plano (RECHAZADO)")

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
