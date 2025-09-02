from pydantic import BaseModel
from typing import Optional
from datetime import date, time, datetime

class AusenciaCreate(BaseModel):
    usuario_email: str
    tipo: str
    subtipo: Optional[str] = None
    fecha_inicio: date
    hora_inicio: Optional[time] = None
    fecha_fin: date
    hora_fin: Optional[time] = None
    parcial: bool = False
    retribuida: bool = True
    motivo: Optional[str] = None

class AusenciaUpdate(BaseModel):
    tipo: Optional[str] = None
    subtipo: Optional[str] = None
    fecha_inicio: Optional[date] = None
    hora_inicio: Optional[time] = None
    fecha_fin: Optional[date] = None
    hora_fin: Optional[time] = None
    parcial: Optional[bool] = None
    retribuida: Optional[bool] = None
    estado: Optional[str] = None
    motivo: Optional[str] = None

class AusenciaOut(BaseModel):
    id: int
    usuario_email: str
    tipo: str
    subtipo: Optional[str] = None
    fecha_inicio: date
    hora_inicio: Optional[time] = None
    fecha_fin: date
    hora_fin: Optional[time] = None
    parcial: bool
    retribuida: bool
    estado: str
    motivo: Optional[str] = None
    creada_por: str
    aprobada_por: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # ➕ nuevo campo para el front
    duracion_segundos: int

    class Config:
        from_attributes = True  # (Pydantic v2). En v1: orm_mode = True
