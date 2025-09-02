# backend/app/routes/ausencias.py
from datetime import date, time as _time
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas_ausencias import AusenciaCreate, AusenciaUpdate, AusenciaOut
from app.auth import get_current_user
from app.models import User, Ausencia
from app import crud

router = APIRouter(prefix="/ausencias", tags=["Ausencias"])


# =========================
# Validaciones / helpers
# =========================
def _validar_payload_creacion(data: AusenciaCreate):
    """Reglas de coherencia de fechas/horas para creación/alias."""
    if not data.parcial:
        # Día completo: horas deben venir vacías
        if data.hora_inicio is not None or data.hora_fin is not None:
            raise HTTPException(status_code=400, detail="Para día completo, hora_inicio y hora_fin deben ser NULL.")
        if data.fecha_fin < data.fecha_inicio:
            raise HTTPException(status_code=400, detail="fecha_fin no puede ser anterior a fecha_inicio.")
        return

    # Parcial
    if data.hora_inicio is None or data.hora_fin is None:
        raise HTTPException(status_code=400, detail="En ausencias parciales, hora_inicio y hora_fin son obligatorias.")
    if data.fecha_fin < data.fecha_inicio:
        raise HTTPException(status_code=400, detail="fecha_fin no puede ser anterior a fecha_inicio.")
    if data.fecha_fin == data.fecha_inicio and data.hora_fin <= data.hora_inicio:
        raise HTTPException(status_code=400, detail="En el mismo día, hora_fin debe ser mayor que hora_inicio.")


def _hay_solape_horas_si_mismo_dia_y_parciales(
    a: Ausencia,
    b_parcial: bool,
    b_fi: date, b_hi: Optional[_time],
    b_ff: date, b_hf: Optional[_time],
) -> bool:
    """
    Devuelve True si hay solape por horas cuando:
    - Ambos son parciales y
    - El rango día de 'a' y 'b' es el mismo día
    """
    if not (a.parcial and b_parcial):
        return False
    if not (a.fecha_inicio == a.fecha_fin == b_fi == b_ff):
        return False

    ai = a.hora_inicio or _time.min
    af = a.hora_fin or _time.max
    bi = b_hi or _time.min
    bf = b_hf or _time.max
    # solape estricto en [inicio, fin)
    return (ai < bf) and (bi < af)


def _bloquear_solapes(db: Session, data: AusenciaCreate):
    """
    Política: impedir solape con APROBADAS y PENDIENTES del mismo usuario.
    Si ambos son parciales y mismo día, se compara por horas. En los demás
    casos, si las fechas se cruzan, se considera solape.
    """
    candidatos = db.query(Ausencia).filter(
        Ausencia.usuario_email == data.usuario_email,
        Ausencia.estado.in_(["APROBADA", "PENDIENTE"]),
        Ausencia.fecha_inicio <= data.fecha_fin,
        Ausencia.fecha_fin >= data.fecha_inicio,
    ).all()

    for a in candidatos:
        # Si ambos parciales y mismo día: miramos horas
        if _hay_solape_horas_si_mismo_dia_y_parciales(
            a, data.parcial, data.fecha_inicio, data.hora_inicio, data.fecha_fin, data.hora_fin
        ):
            raise HTTPException(
                status_code=409,
                detail=f"Existe una ausencia {a.estado.lower()} que se solapa por horas (id={a.id})."
            )
        # En cualquier otro cruce de fechas, tratamos como solape directo
        if not (a.parcial and data.parcial and a.fecha_inicio == a.fecha_fin == data.fecha_inicio == data.fecha_fin):
            raise HTTPException(
                status_code=409,
                detail=f"Existe una ausencia {a.estado.lower()} que solapa con el rango indicado (id={a.id})."
            )


# =========================
# Endpoints
# =========================
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

    # Bloquear solapes (aprobadas/pendientes)
    _bloquear_solapes(db, data)

    return crud.crear_ausencia(db, data, creador_email=current_user.email)


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
    # Empleado: solo sus ausencias. Admin/manager: cualquier usuario
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
    # Solo admin/manager
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


# === Alias frontal: POST /ausencias/crear ===
@router.post("/crear", response_model=AusenciaOut, status_code=status.HTTP_201_CREATED)
def crear_alias(
    data: AusenciaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Misma lógica que en POST base, reutilizando helpers
    if current_user.role not in ("admin", "manager") and data.usuario_email != current_user.email:
        raise HTTPException(status_code=403, detail="No autorizado a crear ausencias para otros usuarios.")

    _validar_payload_creacion(data)
    _bloquear_solapes(db, data)

    return crud.crear_ausencia(db, data, creador_email=current_user.email)


@router.get("/mias", response_model=List[AusenciaOut])
def mis_ausencias(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud.listar_ausencias(db, usuario_email=current_user.email)

