# backend/app/routes/ausencias.py
from datetime import date, time as _time
from typing import Optional, List
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.schemas_ausencias import AusenciaCreate, AusenciaUpdate, AusenciaOut
from app.auth import get_current_user
from app.models import User, Ausencia
from app import crud

router = APIRouter(prefix="/ausencias", tags=["ausencias"])

# =========================
# Debug helper
# =========================
def _dbg(msg: str):
    print(f"[AUSDEBUG] {msg}")

# =========================
# Validaciones / helpers
# =========================
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

# =========================
# Endpoints CRUD
# =========================
@router.post("", response_model=AusenciaOut, status_code=status.HTTP_201_CREATED)
def crear(
    data: AusenciaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _dbg(f"POST /ausencias body={data}")
    try:
        _validar_payload_creacion(data)

        # Permisos: empleado solo puede crear para sí mismo
        if current_user.role not in ("admin", "manager") and data.usuario_email != current_user.email:
            raise HTTPException(status_code=403, detail="No autorizado a crear ausencias para otros usuarios.")

        ausencia = crud.crear_ausencia(db, data, creador_email=current_user.email)
        return ausencia
    except HTTPException:
        raise
    except Exception as e:
        _dbg(f"crear ERROR: {repr(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Error interno creando ausencia")

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
    _dbg(f"GET /ausencias q={{usuario_email:{usuario_email}, estado:{estado}, tipo:{tipo}, desde:{desde}, hasta:{hasta}}} as {current_user.email}|{current_user.role}")
    try:
        # Empleado: solo sus ausencias. Admin/manager: cualquier usuario.
        if current_user.role not in ("admin", "manager"):
            usuario_email = current_user.email

        if desde and hasta and hasta < desde:
            raise HTTPException(status_code=400, detail="El rango de fechas es inválido (hasta < desde).")

        items = crud.listar_ausencias(db, usuario_email, estado, tipo, desde, hasta)
        _dbg(f"GET /ausencias -> {len(items)} filas")
        return items
    except HTTPException:
        raise
    except Exception as e:
        _dbg(f"listar ERROR: {repr(e)}\n{traceback.format_exc()}")
        # Importante: devolver HTTPException para que CORS añada cabeceras y el browser no lo marque como CORS
        raise HTTPException(status_code=500, detail="Error interno listando ausencias")

@router.patch("/{ausencia_id}", response_model=AusenciaOut)
def actualizar(
    ausencia_id: int,
    data: AusenciaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _dbg(f"PATCH /ausencias/{ausencia_id} body={data} by {current_user.email}|{current_user.role}")
    try:
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
    except HTTPException:
        raise
    except Exception as e:
        _dbg(f"actualizar ERROR: {repr(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Error interno actualizando ausencia")

@router.post("/{ausencia_id}/aprobar", response_model=AusenciaOut)
def aprobar(
    ausencia_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _dbg(f"POST /ausencias/{ausencia_id}/aprobar by {current_user.email}|{current_user.role}")
    try:
        if current_user.role not in ("admin", "manager"):
            raise HTTPException(status_code=403, detail="No autorizado")
        aus = crud.aprobar_ausencia(db, ausencia_id, admin_email=current_user.email)
        if not aus:
            raise HTTPException(status_code=404, detail="Ausencia no encontrada")
        return aus
    except HTTPException:
        raise
    except Exception as e:
        _dbg(f"aprobar ERROR: {repr(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Error interno al aprobar la ausencia")

@router.post("/{ausencia_id}/rechazar", response_model=AusenciaOut)
def rechazar(
    ausencia_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _dbg(f"POST /ausencias/{ausencia_id}/rechazar by {current_user.email}|{current_user.role}")
    try:
        if current_user.role not in ("admin", "manager"):
            raise HTTPException(status_code=403, detail="No autorizado")
        aus = crud.rechazar_ausencia(db, ausencia_id, admin_email=current_user.email)
        if not aus:
            raise HTTPException(status_code=404, detail="Ausencia no encontrada")
        return aus
    except HTTPException:
        raise
    except Exception as e:
        _dbg(f"rechazar ERROR: {repr(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Error interno al rechazar la ausencia")

# === ALIAS: POST /ausencias/crear ===
@router.post("/crear", response_model=AusenciaOut, status_code=status.HTTP_201_CREATED)
def crear_alias(
    data: AusenciaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _dbg(f"POST /ausencias/crear body={data} by {current_user.email}|{current_user.role}")
    try:
        if current_user.role not in ("admin", "manager") and data.usuario_email != current_user.email:
            raise HTTPException(status_code=403, detail="No autorizado a crear ausencias para otros usuarios.")

        _validar_payload_creacion(data)

        # control de solapes con APROBADAS y PENDIENTES
        posibles_solapes = db.query(Ausencia).filter(
            Ausencia.usuario_email == data.usuario_email,
            Ausencia.estado.in_(["APROBADA", "PENDIENTE"]),
            Ausencia.fecha_inicio <= data.fecha_fin,
            Ausencia.fecha_fin >= data.fecha_inicio,
        ).all()

        def _hay_solape_horas(a: Ausencia, b_parcial: bool, b_fi, b_hi, b_ff, b_hf) -> bool:
            if not a.parcial or not b_parcial:
                return True
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

        return crud.crear_ausencia(db, data, creador_email=current_user.email)
    except HTTPException:
        raise
    except Exception as e:
        _dbg(f"crear_alias ERROR: {repr(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Error interno creando ausencia")

@router.get("/mias", response_model=List[AusenciaOut])
def mis_ausencias(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _dbg(f"GET /ausencias/mias by {current_user.email}")
    try:
        return crud.listar_ausencias(db, usuario_email=current_user.email)
    except Exception as e:
        _dbg(f"mias ERROR: {repr(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Error interno listando mis ausencias")

# =========================
# READ-ONLY extra (balance/reglas/movs/validar)
# =========================

class _BalanceItem(BaseModel):
    tipo: str
    computo: str
    permite_mediodia: bool
    dias_anuales: float
    asignado: float
    arrastre: float
    mov_delta: float
    bolsa_total: float
    gastado: float
    disponible: float

class _BalanceResponse(BaseModel):
    user_id: int
    anio: int
    saldos: List[_BalanceItem]

class _ReglaItem(BaseModel):
    tipo: str
    computo: str
    permite_mediodia: bool
    dias_anuales: float

class _ReglasResponse(BaseModel):
    user_id: int
    anio: int
    rules: List[_ReglaItem]

class _Movimiento(BaseModel):
    id: int
    saldo_id: int
    fecha: str
    delta: float
    motivo: str
    referencia: Optional[str] = None

class _ValidateBody(BaseModel):
    usuario_id: Optional[int] = None
    usuario_email: Optional[str] = None
    tipo: str
    desde: date
    hasta: date
    medio_dia: bool = False

class _ValidateResponse(BaseModel):
    allowed: bool
    reason: Optional[str] = None
    requested_days: float
    available_days: float
    computo: str
    permite_mediodia: bool

def _resolver_usuario(db: Session, uid: Optional[int], email: Optional[str], fallback: User) -> tuple[int, str]:
    if uid is not None:
        row = db.execute(text("SELECT id, email FROM users WHERE id=:id"), {"id": uid}).first()
        if row:
            return int(row[0]), str(row[1])
    if email:
        row = db.execute(text("SELECT id, email FROM users WHERE email=:e"), {"e": email}).first()
        if row:
            return int(row[0]), str(row[1])
    return fallback.id, fallback.email

@router.get("/balance", response_model=_BalanceResponse)
def balance(
    user_id: Optional[int] = Query(None, ge=1),
    email: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    uid, uemail = _resolver_usuario(db, user_id, email, me)
    anio = year or date.today().year
    _dbg(f"GET /ausencias/balance uid={uid} year={anio}")

    sql = text("""
    WITH u AS (SELECT :uid::int AS id, :uemail::text AS email),
    t AS (
      SELECT s.tipo::text AS tipo
      FROM saldos_ausencia s
      WHERE s.usuario_id = :uid AND s.anio = :anio
    )
    SELECT r.*
    FROM u, t,
         LATERAL public.resumen_ausencia_anual(u.email, :anio, t.tipo) AS r
    ORDER BY r.tipo
    """)
    rows = db.execute(sql, {"uid": uid, "uemail": uemail, "anio": anio}).mappings().all()
    return _BalanceResponse(user_id=uid, anio=anio, saldos=[_BalanceItem(**r) for r in rows])

@router.get("/reglas", response_model=_ReglasResponse)
def reglas(
    user_id: Optional[int] = Query(None, ge=1),
    email: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    uid, _ = _resolver_usuario(db, user_id, email, me)
    anio = year or date.today().year
    _dbg(f"GET /ausencias/reglas uid={uid} year={anio}")

    sql = text("""
      SELECT r.tipo::text AS tipo,
             r.computo::text AS computo,
             r.permite_mediodia,
             r.dias_anuales::numeric AS dias_anuales
      FROM reglas_ausencia r
      JOIN usuarios_convenio uc ON uc.convenio_id = r.convenio_id
      WHERE uc.usuario_id = :uid
      ORDER BY r.tipo
    """)
    rows = db.execute(sql, {"uid": uid}).mappings().all()
    return _ReglasResponse(user_id=uid, anio=anio, rules=[_ReglaItem(**r) for r in rows])

@router.get("/movimientos", response_model=List[_Movimiento])
def movimientos(
    user_id: Optional[int] = Query(None, ge=1),
    email: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    uid, _ = _resolver_usuario(db, user_id, email, me)
    _dbg(f"GET /ausencias/movimientos uid={uid} limit={limit}")

    sql = text("""
      SELECT m.id, m.saldo_id, m.fecha, m.delta,
             m.motivo::text AS motivo, m.referencia
      FROM movimientos_saldo_ausencia m
      JOIN saldos_ausencia s ON s.id = m.saldo_id
      WHERE s.usuario_id = :uid
      ORDER BY m.fecha DESC, m.id DESC
      LIMIT :lim
    """)
    rows = db.execute(sql, {"uid": uid, "lim": limit}).mappings().all()
    return [_Movimiento(**r) for r in rows]

@router.post("/validar", response_model=_ValidateResponse)
def validar(
    body: _ValidateBody,
    db: Session = Depends(get_db),
    me: User = Depends(get_current_user),
):
    uid, uemail = _resolver_usuario(db, body.usuario_id, body.usuario_email, me)
    _dbg(f"POST /ausencias/validar uid={uid} body={body}")

    if body.desde > body.hasta:
        raise HTTPException(status_code=400, detail="rango_fechas_invalido")

    rule = db.execute(text("""
      SELECT r.computo::text AS computo, r.permite_mediodia
      FROM reglas_ausencia r
      JOIN usuarios_convenio uc ON uc.convenio_id = r.convenio_id
      WHERE uc.usuario_id=:uid AND r.tipo::text=:tipo
    """), {"uid": uid, "tipo": body.tipo}).mappings().first()
    if not rule:
        raise HTTPException(status_code=404, detail="regla_no_encontrada")

    computo = rule["computo"]
    permite_mediodia = bool(rule["permite_mediodia"])

    # Días solicitados
    if body.medio_dia:
        requested = 0.5
    else:
        if computo == "LABORABLES":
            requested = float(db.execute(
                text("SELECT public.working_days_for_user(:uid, :d, :h)"),
                {"uid": uid, "d": body.desde, "h": body.hasta}
            ).scalar() or 0)
        else:
            requested = float((body.hasta - body.desde).days + 1)

    if body.medio_dia and not permite_mediodia:
        return _ValidateResponse(
            allowed=False, reason="medio_dia_no_permitido",
            requested_days=requested, available_days=0.0,
            computo=computo, permite_mediodia=permite_mediodia
        )

    anio = body.desde.year
    resumen = db.execute(
        text("SELECT * FROM public.resumen_ausencia_anual(:email, :anio, :tipo)"),
        {"email": uemail, "anio": anio, "tipo": body.tipo}
    ).mappings().first()
    if not resumen:
        raise HTTPException(status_code=404, detail="resumen_no_disponible")

    available = float(resumen.get("disponible") or 0)
    allowed = requested <= available

    return _ValidateResponse(
        allowed=allowed,
        reason=None if allowed else "saldo_insuficiente",
        requested_days=requested,
        available_days=available,
        computo=computo,
        permite_mediodia=permite_mediodia
    )

# =========================
# NUEVO: crear movimiento de saldo (admin/manager)
# =========================
class _MovimientoCreate(BaseModel):
    usuario_id: Optional[int] = None
    usuario_email: Optional[str] = None
    year: Optional[int] = None
    tipo: str
    fecha: date
    delta: float
    motivo: str
    referencia: Optional[str] = None

class _MovimientoCreateOut(BaseModel):
    movimiento: _Movimiento
    balance: _BalanceItem

@router.post("/movimientos", response_model=_MovimientoCreateOut, status_code=status.HTTP_201_CREATED)
def crear_movimiento(
    body: _MovimientoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _dbg(f"POST /ausencias/movimientos body={body} by {current_user.email}|{current_user.role}")
    # Solo admin/manager puede ajustar saldos
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="No autorizado")

    uid, uemail = _resolver_usuario(db, body.usuario_id, body.usuario_email, current_user)
    anio = int(body.year or body.fecha.year)
    tipo = body.tipo

    # Asegura existencia del saldo (si no existe, lo crea a 0)
    saldo_id_sql = text("""
      WITH up AS (
        INSERT INTO saldos_ausencia (usuario_id, anio, tipo, asignado, arrastre)
        SELECT :uid, :anio, :tipo::text, 0, 0
        WHERE NOT EXISTS (
          SELECT 1 FROM saldos_ausencia WHERE usuario_id=:uid AND anio=:anio AND tipo::text=:tipo
        )
        RETURNING id
      )
      SELECT id FROM up
      UNION ALL
      SELECT id FROM saldos_ausencia WHERE usuario_id=:uid AND anio=:anio AND tipo::text=:tipo
      LIMIT 1
    """)
    saldo_id = db.execute(saldo_id_sql, {"uid": uid, "anio": anio, "tipo": tipo}).scalar()
    if not saldo_id:
        raise HTTPException(status_code=500, detail="No se pudo localizar/crear el saldo.")

    # Inserta movimiento
    ins_sql = text("""
      INSERT INTO movimientos_saldo_ausencia (saldo_id, fecha, delta, motivo, referencia)
      VALUES (:sid, :fecha, :delta, :motivo, :ref)
      RETURNING id, saldo_id, fecha::text, delta::numeric, motivo::text, referencia
    """)
    mv = db.execute(ins_sql, {
        "sid": int(saldo_id),
        "fecha": body.fecha,
        "delta": float(body.delta),
        "motivo": body.motivo.strip(),
        "ref": body.referencia
    }).mappings().first()
    db.commit()

    # Relee balance actualizado para ese tipo
    bal_row = db.execute(
        text("SELECT * FROM public.resumen_ausencia_anual(:email, :anio, :tipo)"),
        {"email": uemail, "anio": anio, "tipo": tipo}
    ).mappings().first()
    if not bal_row:
        raise HTTPException(status_code=500, detail="Movimiento creado, pero no se pudo leer el balance.")

    return _MovimientoCreateOut(
        movimiento=_Movimiento(**mv),
        balance=_BalanceItem(**bal_row)
    )
