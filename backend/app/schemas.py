from typing import Optional, Literal
from datetime import date
from pydantic import BaseModel, EmailStr


# =========================
# Usuarios
# =========================
class UserOut(BaseModel):
    id: int
    email: str
    role: str

    class Config:
        from_attributes = True  # (Pydantic v2) reemplaza orm_mode


class RegistroIn(BaseModel):
    email: EmailStr
    password: str
    role: str


class UsuarioUpdate(BaseModel):
    email: str
    role: str


class UsuarioPassword(BaseModel):
    nueva_password: str


# =========================
# Calendario (Festivos + Ausencias unificadas)
# =========================
class CalendarEvent(BaseModel):
    fecha: date
    titulo: str
    type: Literal["FESTIVO", "VACACIONES", "CITA_MEDICA", "AUSENCIA"]
    estado: Optional[Literal["PENDIENTE", "APROBADA", "RECHAZADA"]] = None

    class Config:
        from_attributes = True  # permite crear desde ORM
