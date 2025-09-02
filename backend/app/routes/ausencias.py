# backend/app/routes/ausencias.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional, List

from app.database import get_db
from app.schemas_ausencias import AusenciaCreate, AusenciaUpdate, AusenciaOut
from app.auth import get_current_user
from app.models import User
from app import crud

router = APIRouter(prefix="/ausencias", tags=["Ausencias"])

def _validar_payload_creacion(data: AusenciaCreate):
    # Día completo: horas deben venir vacías
    if not data.parcial:
        if data.hora_inicio is not None or data.hora_fin is not None:
            raise HTTPException(status_code=400, detail="Para día completo, hora_inicio y hora_fin deben ser NULL.")
        if data.fecha_fin < data.fecha_inicio:
            raise HTTPException(status_code=400, detail="fecha_fin no puede ser anterior a fecha_inicio.")
    else:
        # Parcial: horas obligatorias y rango consistente
        if data.hora_inicio is None or data.hora_fin is None:
            raise HTTPException(status_code=400, detail="En ausencias parciales, hora_inicio y hora_fin son obligatorias.")
        if (data.fecha_fin == data.fecha_inicio) and (data.hora_fin <= data.hora_inicio):
            raise HTTPException(status_code=400, detail="En el mismo día, hora_fin debe ser mayor que hora_inicio.")
        if data.fecha_fin < data.fecha_inicio:
            raise HTTPException(status_code=400, detail="fecha_fin no puede ser anterior a fecha_inicio.")

@router.post("", response_model=AusenciaOut, status_code=status.HTTP_201_CREATED)
def crear(
    data: AusenciaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validar_payload_creacion(data)

    # Permisos: empleado solo puede crear para sí mismo
    if current_user.role not in ("admin", "manager") and data.usuario_email != current_user.email:
        raise HTTPException(status_code=403, detail="No autorizado a crear ausencias para otros usuarios.")

    ausencia = crud.crear_ausencia(db, data, creador_email=current_user.email)
    return ausencia

@router.get("", response_model=List[AusenciaOut])
def listar(
    usuario_email: Optional[str] = None,
    estado: Optional[str] = None,
    tipo: Optional[str] = None,
    desde: Optional[date] = Query(None),
    hasta: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Empleado: solo sus ausencias. Admin/manager: cualquier usuario.
    if current_user.role not in ("admin", "manager"):
        usuario_email = current_user.email

    if desde and hasta and hasta < desde:
        raise HTTPException(status_code=400, detail="El rango de fechas es inválido (hasta < desde).")

    return crud.listar_ausencias(db, usuario_email, estado, tipo, desde, hasta)

@router.patch("/{ausencia_id}", response_model=AusenciaOut)
def actualizar(
    ausencia_id: int,
    data: AusenciaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Solo admin/manager o el creador (si quieres permitirlo). Aquí restringimos a admin/manager.
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="No autorizado")

    # Validaciones suaves si modifica fechas/horas
    if data.fecha_inicio and data.fecha_fin and data.fecha_fin < data.fecha_inicio:
        raise HTTPException(status_code=400, detail="fecha_fin no puede ser anterior a fecha_inicio.")
    if (data.hora_inicio is not None) ^ (data.hora_fin is not None):
        raise HTTPException(status_code=400, detail="Si se indica hora_inicio u hora_fin, deben indicarse ambas.")

    aus = crud.actualizar_ausencia(db, ausencia_id, data)
    if not aus:
        raise HTTPException(status_code=404, detail="Ausencia no encontrada")
    return aus

@router.post("/{ausencia_id}/aprobar", response_model=AusenciaOut)
def aprobar(
    ausencia_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="No autorizado")
    aus = crud.aprobar_ausencia(db, ausencia_id, admin_email=current_user.email)
    if not aus:
        raise HTTPException(status_code=404, detail="Ausencia no encontrada")
    return aus

@router.post("/{ausencia_id}/rechazar", response_model=AusenciaOut)
def rechazar(
    ausencia_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="No autorizado")
    aus = crud.rechazar_ausencia(db, ausencia_id, admin_email=current_user.email)
    if not aus:
        raise HTTPException(status_code=404, detail="Ausencia no encontrada")
    return aus

# === ALIAS: POST /ausencias/crear ===
from fastapi import status
from datetime import datetime, time as _time
from app.auth import get_current_user
from app.models import User, Ausencia

@router.post("/crear", response_model=AusenciaOut, status_code=status.HTTP_201_CREATED)
def crear_alias(
    data: AusenciaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Alias de creación para front: POST /ausencias/crear
    - Empleado solo puede crear para sí mismo.
    - Admin/Manager pueden crear para cualquiera.
    - Valida coherencia de fechas/horas.
    - Bloquea solape con ausencias ya APROBADAS (y, opcionalmente, pendientes).
    """
    # ---- permisos ----
    if current_user.role not in ("admin", "manager") and data.usuario_email != current_user.email:
        raise HTTPException(status_code=403, detail="No autorizado a crear ausencias para otros usuarios.")

    # ---- validaciones de payload (mismas reglas que en el POST base) ----
    if not data.parcial:
        if data.hora_inicio is not None or data.hora_fin is not None:
            raise HTTPException(status_code=400, detail="Para día completo, hora_inicio y hora_fin deben ser NULL.")
        if data.fecha_fin < data.fecha_inicio:
            raise HTTPException(status_code=400, detail="fecha_fin no puede ser anterior a fecha_inicio.")
    else:
        if data.hora_inicio is None or data.hora_fin is None:
            raise HTTPException(status_code=400, detail="En ausencias parciales, hora_inicio y hora_fin son obligatorias.")
        if data.fecha_fin < data.fecha_inicio:
            raise HTTPException(status_code=400, detail="fecha_fin no puede ser anterior a fecha_inicio.")
        if data.fecha_fin == data.fecha_inicio and data.hora_fin <= data.hora_inicio:
            raise HTTPException(status_code=400, detail="En el mismo día, hora_fin debe ser mayor que hora_inicio.")

    # ---- control de solapes con ausencias ya registradas ----
    # Política: no permitir solape con APROBADAS (y opcionalmente PENDIENTES). Aquí bloqueamos ambas.
    posibles_solapes = db.query(Ausencia).filter(
        Ausencia.usuario_email == data.usuario_email,
        Ausencia.estado.in_(["APROBADA", "PENDIENTE"]),
        Ausencia.fecha_inicio <= data.fecha_fin,
        Ausencia.fecha_fin >= data.fecha_inicio,
    ).all()

    def _hay_solape_horas(a: Ausencia, b_parcial: bool, b_fi, b_hi, b_ff, b_hf) -> bool:
        # Si alguno es de día completo, consideramos que solapa.
        if not a.parcial or not b_parcial:
            return True
        # Mismo día: comprobar horas; si son días distintos dentro del rango, lo tratamos como solape.
        # Aquí solo detallamos el caso mismo día para refinar.
        if a.fecha_inicio == a.fecha_fin == b_fi == b_ff:
            ai = a.hora_inicio or _time.min
            af = a.hora_fin or _time.max
            bi = b_hi or _time.min
            bf = b_hf or _time.max
            return (ai < bf) and (bi < af)
        return True

    for a in posibles_solapes:
        # Si rangos de fecha se cruzan, afinamos por horas solo si ambos son parciales y mismo día.
        if _hay_solape_horas(a, data.parcial, data.fecha_inicio, data.hora_inicio, data.fecha_fin, data.hora_fin):
            raise HTTPException(
                status_code=409,
                detail=f"Existe una ausencia {a.estado.lower()} que solapa con el rango indicado (id={a.id})."
            )

    # ---- crear ----
    return crud.crear_ausencia(db, data, creador_email=current_user.email)

@router.get("/mias", response_model=List[AusenciaOut])
def mis_ausencias(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud.listar_ausencias(db, usuario_email=current_user.email)

