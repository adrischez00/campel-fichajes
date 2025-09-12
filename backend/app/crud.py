from __future__ import annotations

from datetime import datetime, timedelta, date, time as _time
from collections import defaultdict
from typing import Optional, List, Dict
import re

import pytz
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text, func
from sqlalchemy.exc import SQLAlchemyError

from app import models
from app.utils import generar_hash_fichaje, log_evento
from app.schemas_solicitudes import SolicitudManualCreate, SolicitudFiltro
from app.config import HORAS_JORNADA_COMPLETA
from app.models import Ausencia, LogAuditoria
from app.schemas_ausencias import AusenciaCreate, AusenciaUpdate


# ======================== TZ & helpers ========================
TZ_MADRID = pytz.timezone("Europe/Madrid")
_VALID_TIPOS = {"entrada", "salida"}

def _ensure_aware(dt: Optional[datetime], tz=TZ_MADRID) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return tz.localize(dt)
    return dt.astimezone(tz)

def _safe_iso(dt: Optional[datetime]) -> Optional[str]:
    dt = _ensure_aware(dt)
    return dt.isoformat() if dt else None

# ======================== Usuarios ========================
def _normalize_email_for_compare(e: str) -> str:
    # quita TODO tipo de espacios (incl. NBSP) y pasa a lower
    return re.sub(r"\s+", "", (e or "")).replace("\u00A0", "").lower()

def obtener_usuario_por_email(db: Session, email: str):
    """
    Búsqueda robusta:
      - normaliza la entrada (quita espacios, NBSP, lower)
      - en BD elimina \s+ y NBSP antes de comparar (PostgreSQL: regexp_replace + replace)
    """
    if not email:
        return None
    norm = _normalize_email_for_compare(email)

    # email_sin_nbsp = REPLACE(email, NBSP, '')
    email_sin_nbsp = func.replace(models.User.email, "\u00A0", "")
    # email_compact = REGEXP_REPLACE(email_sin_nbsp, '\s+', '', 'g')
    email_compact = func.regexp_replace(email_sin_nbsp, r"\s+", "", "g")

    return (
        db.query(models.User)
        .filter(func.lower(email_compact) == norm)
        .first()
    )

def obtener_usuario_por_id(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()

def crear_usuario(db: Session, email: str, password: str, role: str = "employee"):
    from app import auth
    hashed_pw = auth.hashear_password(password)
    usuario = models.User(email=email.strip(), hashed_password=hashed_pw, role=role)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario

def autenticar_usuario(db: Session, email: str, password: str):
    """
    Autenticación tolerante:
      - busca con email normalizado
      - acepta hash en columnas legacy (hashed_password / password_hash / password)
      - hace strip() del hash antes de verificar
    """
    from app import auth
    usuario = obtener_usuario_por_email(db, email)
    if not usuario:
        return None

    hashed = (
        getattr(usuario, "hashed_password", None)
        or getattr(usuario, "password_hash", None)
        or getattr(usuario, "password", None)
    )
    if isinstance(hashed, str):
        hashed = hashed.strip()

    if not hashed or not auth.verificar_password(password, hashed):
        return None
    return usuario

def obtener_usuarios(db: Session):
    return db.query(models.User).all()

# ========================
#  Fichajes
# ========================
def _ausencias_aprobadas_en_instante(db: Session, email: str, t: datetime):
    d = _ensure_aware(t, TZ_MADRID).date()
    return db.query(Ausencia).filter(
        Ausencia.usuario_email == email,
        Ausencia.estado == "APROBADA",
        Ausencia.fecha_inicio <= d,
        Ausencia.fecha_fin >= d
    ).all()

def _instante_en_parcial(a: Ausencia, t: datetime, tz=TZ_MADRID) -> bool:
    if not a.parcial:
        return False
    dia = _ensure_aware(t, tz).date()
    ini = datetime.combine(
        dia,
        a.hora_inicio if (dia == a.fecha_inicio and a.hora_inicio) else _time.min
    )
    fin = datetime.combine(
        dia,
        a.hora_fin if (dia == a.fecha_fin and a.hora_fin) else _time.max
    )
    ini = _ensure_aware(ini, tz)
    fin = _ensure_aware(fin, tz)
    t = _ensure_aware(t, tz)
    return ini <= t <= fin

# === AUTOCIERRE ASISTIDO
def _autocerrar_turno_con_solicitud_salida(db: Session, usuario: models.User, ultima_entrada_dt: datetime):
    ahora = datetime.now(TZ_MADRID)
    sol = (
        db.query(models.SolicitudManual)
        .filter(
            models.SolicitudManual.user_id == usuario.id,
            models.SolicitudManual.tipo.ilike("salida"),
            models.SolicitudManual.estado.in_(["pendiente", "aprobada"]),
            models.SolicitudManual.timestamp >= ultima_entrada_dt,
            models.SolicitudManual.timestamp <= ahora,
        )
        .order_by(models.SolicitudManual.timestamp.asc())
        .first()
    )
    if not sol:
        return None

    ts = _ensure_aware(sol.timestamp, TZ_MADRID)

    ya = (
        db.query(models.Fichaje)
        .filter(
            models.Fichaje.user_id == usuario.id,
            models.Fichaje.tipo == "salida",
            or_(
                models.Fichaje.timestamp == ts,
                models.Fichaje.solicitud_id == sol.id
            ),
        )
        .first()
    )
    if ya:
        return ya

    hash_val = generar_hash_fichaje(usuario.email, "salida", ts.isoformat())
    validez = "valido" if (sol.estado or "").lower() == "aprobada" else "provisional"

    fich = models.Fichaje(
        tipo="salida",
        timestamp=ts,
        hash=hash_val,
        usuario=usuario,
        is_manual=True,
        motivo=f"[asistido por solicitud #{sol.id}] {sol.motivo or ''}".strip(),
        validez=validez,
        solicitud_id=sol.id,
    )
    db.add(fich)
    log_evento(db, usuario, "fichaje", f"salida (asistido: {validez})")
    db.commit()
    db.refresh(fich)
    return fich

def crear_fichaje(db: Session, tipo: str, usuario: models.User):
    tipo_norm = (tipo or "").strip().lower()
    if tipo_norm not in _VALID_TIPOS:
        raise ValueError("Tipo de fichaje inválido. Usa 'entrada' o 'salida'.")

    ahora = datetime.now(TZ_MADRID)

    # Bloqueos por ausencias aprobadas
    aus = _ausencias_aprobadas_en_instante(db, usuario.email, ahora)
    for a in aus:
        if (a.tipo or "").upper() == "VACACIONES" and not a.parcial and a.retribuida:
            raise ValueError("❌ No puedes fichar: tienes VACACIONES retribuidas aprobadas hoy.")
        if a.retribuida and not a.parcial and (a.tipo or "").upper() != "VACACIONES":
            raise ValueError(f"❌ No puedes fichar: ausencia retribuida aprobada hoy ({a.tipo}).")
        if a.parcial and _instante_en_parcial(a, ahora):
            rango = []
            if a.hora_inicio: rango.append(a.hora_inicio.strftime("%H:%M"))
            if a.hora_fin: rango.append(a.hora_fin.strftime("%H:%M"))
            detalle = " - ".join(rango) if rango else "tramo parcial"
            raise ValueError(f"❌ No puedes fichar dentro de una ausencia parcial aprobada ({detalle}).")

    ultimo = (
        db.query(models.Fichaje)
        .filter(models.Fichaje.user_id == usuario.id)
        .order_by(models.Fichaje.timestamp.desc())
        .first()
    )

    if ultimo and (ultimo.tipo or "").lower() == tipo_norm:
        if tipo_norm == "entrada" and (ultimo.tipo or "").lower() == "entrada":
            cerrada = _autocerrar_turno_con_solicitud_salida(
                db, usuario, _ensure_aware(ultimo.timestamp, TZ_MADRID)
            )
            if cerrada:
                ultimo = (
                    db.query(models.Fichaje)
                    .filter(models.Fichaje.user_id == usuario.id)
                    .order_by(models.Fichaje.timestamp.desc())
                    .first()
                )
            else:
                raise ValueError("❌ Ya tienes un turno abierto. Solicita primero una SALIDA manual (pendiente o aprobada) para cerrarlo.")
        else:
            raise ValueError(f"❌ Ya existe un fichaje de tipo '{tipo_norm}' justo antes.")

    if tipo_norm == "salida":
        tiene_entrada_previa = (
            db.query(models.Fichaje)
            .filter(models.Fichaje.user_id == usuario.id, models.Fichaje.tipo == "entrada")
            .first()
            is not None
        )
        if not tiene_entrada_previa:
            raise ValueError("❌ No puedes fichar salida sin una entrada previa.")

    hash_val = generar_hash_fichaje(usuario.email, tipo_norm, ahora.isoformat())
    fichaje = models.Fichaje(
        tipo=tipo_norm,
        timestamp=ahora,
        hash=hash_val,
        usuario=usuario,
        # validez='valido' por defecto
    )
    db.add(fichaje)
    log_evento(db, usuario, "fichaje", tipo_norm)
    db.commit()
    db.refresh(fichaje)
    return fichaje

def obtener_fichajes_usuario(db: Session, usuario: models.User):
    fichajes = (
        db.query(models.Fichaje)
        .filter(models.Fichaje.user_id == usuario.id)
        .order_by(models.Fichaje.timestamp.desc())
        .all()
    )
    return [
        {
            "id": f.id,
            "tipo": f.tipo,
            "timestamp": _safe_iso(f.timestamp),
            "hash": f.hash,
            "usuario_email": usuario.email,
            "is_manual": bool(getattr(f, "is_manual", False)),
            "validez": (getattr(f, "validez", "valido") or "valido"),
            "solicitud_id": getattr(f, "solicitud_id", None),
        }
        for f in fichajes
    ]

# ========================
#  Solicitudes Manuales
# ========================
def _parse_fecha_hora(fecha: str, hora: str, tz=TZ_MADRID) -> datetime:
    hora = (hora or "").strip()
    if len(hora.split(":")) == 2:
        hora += ":00"
    ts_str = f"{fecha} {hora}"
    for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return _ensure_aware(datetime.strptime(ts_str, fmt), tz)
        except ValueError:
            continue
    raise ValueError("Formato de fecha/hora inválido. Usa dd/mm/YYYY o YYYY-mm-dd y HH:MM[:SS].")

def crear_solicitud_manual(db: Session, data: SolicitudManualCreate, usuario: models.User):
    ts = _parse_fecha_hora(data.fecha, data.hora, TZ_MADRID)
    if ts > datetime.now(TZ_MADRID):
        raise ValueError("❌ No puedes solicitar un fichaje con fecha/hora futura.")
    solicitud = models.SolicitudManual(
        fecha=data.fecha.strip(),
        hora=data.hora.strip(),
        tipo=(data.tipo or "").strip().lower(),
        motivo=(data.motivo or "").strip(),
        estado="pendiente",
        timestamp=ts,
        usuario=usuario,
    )
    db.add(solicitud)
    log_evento(db, usuario, "solicitud manual", f"{data.tipo} {data.fecha} {data.hora}")
    db.commit()
    db.refresh(solicitud)
    return solicitud

def listar_solicitudes_avanzado(
    db: Session,
    filtro: Optional[SolicitudFiltro] = None,
    solo_pendientes: bool = False,
):
    q = db.query(models.SolicitudManual).join(models.User)

    if filtro:
        if filtro.estado:
            q = q.filter(models.SolicitudManual.estado == filtro.estado.value)
        if filtro.usuario:
            q = q.filter(models.User.email == str(filtro.usuario))
        if filtro.tipo:
            q = q.filter(models.SolicitudManual.tipo == filtro.tipo)
        if filtro.desde:
            q = q.filter(models.SolicitudManual.timestamp >= filtro.desde)
        if filtro.hasta:
            q = q.filter(models.SolicitudManual.timestamp <= filtro.hasta)
        if solo_pendientes:
            q = q.filter(models.SolicitudManual.estado == "pendiente")

        order_map = {
            "timestamp": models.SolicitudManual.timestamp,
            "fecha": models.SolicitudManual.timestamp,
            "usuario": models.User.email,
            "estado": models.SolicitudManual.estado,
        }
        col = order_map.get(filtro.order_by, models.SolicitudManual.timestamp)
        q = q.order_by(col.desc() if filtro.order_dir.value == "desc" else col.asc())

        total = q.count()
        page = max(1, int(filtro.page))
        per_page = max(1, min(200, int(filtro.per_page)))
        q = q.offset((page - 1) * per_page).limit(per_page)
    else:
        if solo_pendientes:
            q = q.filter(models.SolicitudManual.estado == "pendiente")
        q = q.order_by(models.SolicitudManual.timestamp.desc())
        total = q.count()
        page, per_page = 1, total or 1

    items = []
    for s in q.all():
        gp = getattr(s, "gestionado_por", None)
        items.append({
            "id": s.id,
            "fecha": s.fecha,
            "hora": s.hora,
            "tipo": s.tipo,
            "motivo": s.motivo,
            "estado": s.estado,
            "timestamp": _safe_iso(s.timestamp),
            "usuario_email": getattr(s.usuario, "email", "desconocido"),
            "gestionado_por_id": getattr(s, "gestionado_por_id", None),
            "gestionado_por_email": getattr(gp, "email", None) if gp else None,
            "gestionado_en": _safe_iso(getattr(s, "gestionado_en", None)),
            "motivo_rechazo": getattr(s, "motivo_rechazo", None),
            "ip_origen": getattr(s, "ip_origen", None),
        })

    return {"items": items, "total": total, "page": page, "per_page": per_page}

def listar_solicitudes(db: Session):
    return listar_solicitudes_avanzado(db, None)["items"]

def aprobar_solicitud(db: Session, solicitud_id: int, admin: models.User, ip: Optional[str] = None):
    s = db.query(models.SolicitudManual).filter(models.SolicitudManual.id == solicitud_id).first()
    if not s:
        raise ValueError("Solicitud no encontrada")
    if s.estado != "pendiente":
        raise ValueError("La solicitud ya fue gestionada")

    ts = _parse_fecha_hora(s.fecha, s.hora, TZ_MADRID)

    fich = (
        db.query(models.Fichaje)
        .filter(
            models.Fichaje.user_id == s.user_id,
            models.Fichaje.tipo == s.tipo.lower(),
            or_(models.Fichaje.solicitud_id == s.id, models.Fichaje.timestamp == ts),
        )
        .order_by(models.Fichaje.id.asc())
        .first()
    )

    if fich:
        if s.tipo.lower() == "salida":
            entrada_ok = (
                db.query(models.Fichaje)
                .filter(
                    models.Fichaje.user_id == s.user_id,
                    models.Fichaje.tipo == "entrada",
                    models.Fichaje.timestamp <= fich.timestamp,
                )
                .order_by(models.Fichaje.timestamp.desc())
                .first()
            )
            if not entrada_ok:
                raise ValueError("❌ No hay una entrada previa válida para esa salida.")
        fich.validez = "valido"
        fich.solicitud_id = s.id
        db.add(fich)
    else:
        hash_val = generar_hash_fichaje(s.usuario.email, (s.tipo or "").lower(), ts.isoformat())
        fich = models.Fichaje(
            tipo=(s.tipo or "").lower(),
            timestamp=ts,
            hash=hash_val,
            usuario=s.usuario,
            is_manual=True,
            motivo=s.motivo,
            validez="valido",
            solicitud_id=s.id,
        )
        if fich.tipo == "salida":
            entrada_ok = (
                db.query(models.Fichaje)
                .filter(
                    models.Fichaje.user_id == s.user_id,
                    models.Fichaje.tipo == "entrada",
                    models.Fichaje.timestamp <= fich.timestamp,
                )
                .order_by(models.Fichaje.timestamp.desc())
                .first()
            )
            if not entrada_ok:
                raise ValueError("❌ No hay una entrada previa válida para esa salida.")
        db.add(fich)

    s.estado = "aprobada"
    if admin and hasattr(s, "gestionado_por_id"):
        s.gestionado_por_id = admin.id
    if hasattr(s, "gestionado_en"):
        s.gestionado_en = datetime.now(pytz.UTC)
    if hasattr(s, "ip_origen"):
        s.ip_origen = ip

    log_evento(db, s.usuario, "fichaje manual aprobado",
               f"{ts.strftime('%d/%m/%Y %H:%M:%S')}|{s.motivo}")

    db.commit()
    db.refresh(s)
    return s

def rechazar_solicitud(db: Session, solicitud_id: int, admin: models.User, motivo_rechazo: str, ip: Optional[str] = None):
    motivo = (motivo_rechazo or "").strip()
    s = db.query(models.SolicitudManual).filter(models.SolicitudManual.id == solicitud_id).first()
    if not s:
        raise ValueError("Solicitud no encontrada")
    if s.estado != "pendiente":
        raise ValueError("La solicitud ya fue gestionada")

    fich = (
        db.query(models.Fichaje)
        .filter(
            models.Fichaje.user_id == s.user_id,
            models.Fichaje.solicitud_id == s.id
        )
        .first()
    )
    if fich:
        fich.validez = "invalidado"
        db.add(fich)

    s.estado = "rechazada"
    if hasattr(s, "motivo_rechazo"):
        s.motivo_rechazo = motivo if motivo else None
    if admin and hasattr(s, "gestionado_por_id"):
        s.gestionado_por_id = admin.id
    if hasattr(s, "gestionado_en"):
        s.gestionado_en = datetime.now(pytz.UTC)
    if hasattr(s, "ip_origen"):
        s.ip_origen = ip

    log_evento(db, s.usuario, "fichaje manual rechazado", s.motivo)

    db.commit()
    db.refresh(s)
    return s

# ========================
#  Logs (para UI)
# ========================
def obtener_logs(db: Session):
    fichajes = (
        db.query(models.Fichaje)
        .join(models.User)
        .order_by(models.Fichaje.timestamp.asc())
        .all()
    )

    resultado = []
    for f in fichajes:
        if not f.usuario:
            continue
        resultado.append({
            "usuario_email": f.usuario.email,
            "tipo": f.tipo,
            "timestamp": _safe_iso(f.timestamp),
            "is_manual": bool(getattr(f, "is_manual", False)),
            "validez": (getattr(f, "validez", "valido") or "valido"),
            "motivo": (getattr(f, "motivo", "") or "").strip() if getattr(f, "is_manual", False) else ""
        })
    return resultado

# (resto de helpers y calendario igual que ya tenías)
