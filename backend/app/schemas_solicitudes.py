# backend/app/schemas_solicitudes.py

from pydantic import BaseModel, Field, EmailStr
from typing import Literal, Optional, List
from datetime import datetime
from enum import Enum

# --- Enums ---
class SolicitudEstado(str, Enum):
    pendiente = "pendiente"
    aprobada = "aprobada"
    rechazada = "rechazada"

class OrdenDir(str, Enum):
    asc = "asc"
    desc = "desc"

# --- Entrada ---
class SolicitudManualCreate(BaseModel):
    fecha: str = Field(..., example="22/07/2025")  # Puede venir en dd/mm/YYYY o YYYY-mm-dd
    hora: str = Field(..., example="08:00")
    tipo: Literal["entrada", "salida"]
    motivo: str

# Compatibilidad con tu flujo actual
class ResolverSolicitudIn(BaseModel):
    id: int
    aprobar: bool
    motivo_rechazo: Optional[str] = None  # si aprobar=False, se recomienda enviar motivo

# --- Filtros para listar ---
class SolicitudFiltro(BaseModel):
    estado: Optional[SolicitudEstado] = None
    usuario: Optional[EmailStr] = None        # email del solicitante
    desde: Optional[datetime] = None          # filtra por timestamp (creación)
    hasta: Optional[datetime] = None
    tipo: Optional[Literal["entrada", "salida"]] = None
    order_by: Literal["timestamp", "fecha", "usuario", "estado"] = "timestamp"
    order_dir: OrdenDir = "desc"
    page: int = 1
    per_page: int = 15

# --- Salida ---
class SolicitudOut(BaseModel):
    id: int
    user_id: int
    usuario_email: EmailStr

    fecha: str
    hora: str
    tipo: Literal["entrada", "salida"]
    motivo: str

    estado: SolicitudEstado
    timestamp: datetime

    # Auditoría
    gestionado_por_id: Optional[int] = None
    gestionado_por_email: Optional[EmailStr] = None
    gestionado_en: Optional[datetime] = None
    motivo_rechazo: Optional[str] = None
    ip_origen: Optional[str] = None

class Config:
    from_attributes = True

class SolicitudesListado(BaseModel):
    items: List[SolicitudOut]
    total: int
    page: int
    per_page: int

