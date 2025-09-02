# backend/app/auth_tokens.py
from datetime import datetime, timedelta, timezone
import os, secrets, jwt  # pyjwt

ALGO = "HS256"
ACCESS_MIN = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "30"))

# Usa secretos distintos; si no están en env, genera aleatorios (dev)
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", secrets.token_urlsafe(32))

def create_access_token(subject: str, minutes: int = ACCESS_MIN) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=minutes)
    payload = {"sub": subject, "type": "access", "exp": int(exp.timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGO)

def create_refresh_token(subject: str, days: int = REFRESH_DAYS) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=days)
    payload = {"sub": subject, "type": "refresh", "exp": int(exp.timestamp())}
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=ALGO)

def decode_access(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[ALGO])

def decode_refresh(token: str) -> dict:
    return jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[ALGO])
