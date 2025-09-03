# backend/app/routes/ausencias.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import date, time as _time
from typing import Optional, List

from pydantic import BaseModel, Field

from app.database import get_db
from app.schemas_ausencias import AusenciaCreate, AusenciaUpdate, AusenciaOut
from app.auth import get_current_user
from app.models import User, Ausencia, SaldoAusencia, TipoAusenciaEnum
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

    try:
        ausencia = crud.crear_ausencia(db, data, creador_email=current_user.email)
        return ausencia
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    # Solo admin/manager
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="No autorizado")

    # Validaciones suaves si modifica fechas/horas
    if data.fecha_inicio and data.fecha_fin and data.fecha_fin < data.fecha_inicio:
        raise HTTPException(status_code=400, detail="fecha_fin no puede ser anterior a fecha_inicio.")
    if (data.hora_inicio is not None) ^ (data.hora_fin is not None):
        raise HTTPException(status_code=400, detail="Si se indica hora_inicio u hora_fin, deben indicarse ambas.")

    try:
        aus = crud.actualizar_ausencia(db, ausencia_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
    try:
        aus = crud.aprobar_ausencia(db, ausencia_id, admin_email=current_user.email)
    except ValueError as e:
        # Ej: saldo insuficiente o solapes
        raise HTTPException(status_code=400, detail=str(e))
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
    - Bloquea solape con ausencias ya APROBADAS (y PENDIENTES).
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
        # Mismo día: comprobar horas; si son días distintos dentro del rango, también solapa por tramo.
        if a.fecha_inicio == a.fecha_fin == b_fi == b_ff:
            ai = a.hora_inicio or _time.min
            af = a.hora_fin or _time.max
            bi = b_hi or _time.min
            bf = b_hf or _time.max
            return (ai < bf) and (bi < af)
        return True

    for a in posibles_solapes:
        if _hay_solape_horas(a, data.parcial, data.fecha_inicio, data.hora_inicio, data.fecha_fin, data.hora_fin):
            raise HTTPException(
                status_code=409,
                detail=f"Existe una ausencia {a.estado.lower()} que solapa con el rango indicado (id={a.id})."
            )

    # ---- crear ----
    try:
        return crud.crear_ausencia(db, data, creador_email=current_user.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/mias", response_model=List[AusenciaOut])
def mis_ausencias(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud.listar_ausencias(db, usuario_email=current_user.email)


# ============================
# NUEVO: Previsualización de consumo
# ============================
@router.get("/calcular")
def previsualizar_calculo(
    usuario_email: str = Query(..., description="Email del usuario dueño de la ausencia"),
    tipo: str = Query(..., description="Tipo de ausencia (VACACIONES, ASUNTOS_PROPIOS, etc.)"),
    fecha_inicio: date = Query(...),
    fecha_fin: date = Query(...),
    parcial: bool = Query(False),
    hora_inicio: Optional[_time] = Query(None),
    hora_fin: Optional[_time] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Permisos: empleado solo puede calcular para sí mismo
    if current_user.role not in ("admin", "manager") and usuario_email != current_user.email:
        raise HTTPException(status_code=403, detail="No autorizado")

    # Reglas rápidas de coherencia
    if fecha_fin < fecha_inicio:
        raise HTTPException(status_code=400, detail="fecha_fin no puede ser anterior a fecha_inicio.")
    if parcial and (hora_inicio is None or hora_fin is None):
        raise HTTPException(status_code=400, detail="En ausencias parciales, hora_inicio y hora_fin son obligatorias.")
    if parcial and fecha_inicio == fecha_fin and hora_fin <= hora_inicio:
        raise HTTPException(status_code=400, detail="En el mismo día, hora_fin debe ser mayor que hora_inicio.")

    try:
        data = crud.previsualizar_consumo_ausencia(
            db=db,
            usuario_email=usuario_email,
            tipo=tipo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            parcial=parcial,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
        )
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================
# NUEVO: KPIs de saldos
# ============================
def _saldos_usuario_anio(db: Session, usuario_id: int, anio: Optional[int] = None):
    anio = anio or date.today().year
    saldos = (
        db.query(SaldoAusencia)
        .filter(SaldoAusencia.usuario_id == usuario_id, SaldoAusencia.anio == anio)
        .all()
    )
    items = []
    for s in saldos:
        asignado = float(s.asignado or 0)
        arrastre = float(s.arrastre or 0)
        gastado = float(s.gastado or 0)
        disponible = (asignado + arrastre) - gastado
        items.append({
            "tipo": s.tipo.value if hasattr(s.tipo, "value") else str(s.tipo),
            "asignado": asignado,
            "arrastre": arrastre,
            "gastado": gastado,
            "disponible": disponible,
        })
    return {"anio": anio, "saldos": items}


@router.get("/saldos/{usuario_id}")
def get_saldos_usuario(
    usuario_id: int,
    anio: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Permisos: empleado solo puede ver los suyos
    if current_user.role not in ("admin", "manager") and current_user.id != usuario_id:
        raise HTTPException(status_code=403, detail="No autorizado")

    return _saldos_usuario_anio(db, usuario_id, anio)


@router.get("/saldos/me")
def get_mis_saldos(
    anio: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _saldos_usuario_anio(db, current_user.id, anio)


# ============================
# NUEVO: Endpoint admin — Ajuste de saldos
# ============================
class AjusteSaldoIn(BaseModel):
    usuario_id: int = Field(..., gt=0)
    tipo: TipoAusenciaEnum = Field(..., description="Tipo de ausencia: VACACIONES, ASUNTOS_PROPIOS, ...")
    anio: Optional[int] = Field(None, ge=1970, le=2100)
    delta: float = Field(..., description="Días a sumar o restar en el ASIGNADO (p. ej., +2, -1.5)")
    comentario: Optional[str] = Field(None, max_length=50)


@router.post("/saldos/ajuste")
def ajustar_saldo_endpoint(
    payload: AjusteSaldoIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin/Manager: ajusta el 'asignado' del saldo anual del usuario.
    - delta>0 suma asignado; delta<0 resta asignado.
    - Valida que no deje el disponible en negativo.
    - Registra un MovimientoSaldoAusencia con motivo=AJUSTE.
    """
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="No autorizado")

    if payload.delta == 0:
        raise HTTPException(status_code=400, detail="El delta de ajuste no puede ser 0.")

    anio = payload.anio or date.today().year
    tipo_str = payload.tipo.value  # validado por pydantic como Enum

    try:
        resultado = crud.ajustar_saldo(
            db=db,
            usuario_id=payload.usuario_id,
            tipo=tipo_str,
            anio=anio,
            delta=float(payload.delta),
            comentario=payload.comentario,
        )
        # Devolver también KPIs del año para refresco inmediato en front
        kpis = _saldos_usuario_anio(db, payload.usuario_id, anio)
        return {"ok": True, "resultado": resultado, "kpis": kpis}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

