# app/crud.py  — versión consolidada y corregida
from __future__ import annotations

from datetime import datetime, timedelta, date, time as _time
from collections import defaultdict
from typing import Optional, List, Dict

import pytz
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from sqlalchemy.exc import SQLAlchemyError

from app import models
from app.utils import generar_hash_fichaje, log_evento
from app.schemas_solicitudes import SolicitudManualCreate, SolicitudFiltro
from app.config import HORAS_JORNADA_COMPLETA
from app.schemas_ausencias import AusenciaCreate, AusenciaUpdate

# ——— Convenios / Saldos ———
from app.models import (
    Ausencia,
    LogAuditoria,
    SaldoAusencia,
    MovimientoSaldoAusencia,
    MotivoMovimientoEnum,
    ReglaAusencia,
    UsuarioConvenio,
    TipoAusenciaEnum,
    ComputoDiasEnum,
    CalendarMark,
    UserLocation,
)

# ========================
#  Zona horaria
# ========================
TZ_MADRID = pytz.timezone("Europe/Madrid")
_VALID_TIPOS = {"entrada", "salida"}


# ========================
#  Helpers generales
# ========================
def _ensure_aware(dt: Optional[datetime], tz=TZ_MADRID) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return tz.localize(dt)
    return dt.astimezone(tz)


def _safe_iso(dt: Optional[datetime]) -> Optional[str]:
    dt = _ensure_aware(dt)
    return dt.isoformat() if dt else None


# ========================
#  Usuarios
# ========================
def obtener_usuario_por_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def obtener_usuario_por_id(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def crear_usuario(db: Session, email: str, password: str, role: str = "employee"):
    from app import auth
    hashed_pw = auth.hashear_password(password)
    usuario = models.User(email=email, hashed_password=hashed_pw, role=role)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def autenticar_usuario(db: Session, email: str, password: str):
    from app import auth
    usuario = obtener_usuario_por_email(db, email)
    if not usuario:
        return None
    if not auth.verificar_password(password, usuario.hashed_password):
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


def crear_fichaje(db: Session, tipo: str, usuario: models.User):
    tipo_norm = (tipo or "").strip().lower()
    if tipo_norm not in _VALID_TIPOS:
        raise ValueError("Tipo de fichaje inválido. Usa 'entrada' o 'salida'.")

    ahora = datetime.now(TZ_MADRID)

    # Bloqueo por ausencias/vacaciones aprobadas
    aus = _ausencias_aprobadas_en_instante(db, usuario.email, ahora)
    for a in aus:
        if (a.tipo or "").upper() == "VACACIONES" and not a.parcial and a.retribuida:
            raise ValueError("❌ No puedes fichar: tienes VACACIONES retribuidas aprobadas hoy.")
        if a.retribuida and not a.parcial and (a.tipo or "").upper() != "VACACIONES":
            raise ValueError(f"❌ No puedes fichar: existe una ausencia retribuida aprobada hoy ({a.tipo}).")
        if a.parcial and _instante_en_parcial(a, ahora):
            rango = []
            if a.hora_inicio:
                rango.append(a.hora_inicio.strftime("%H:%M"))
            if a.hora_fin:
                rango.append(a.hora_fin.strftime("%H:%M"))
            detalle = " - ".join(rango) if rango else "tramo parcial"
            raise ValueError(f"❌ No puedes fichar dentro de una ausencia parcial aprobada ({detalle}).")

    # No permitir dos iguales seguidas
    ultimo = (
        db.query(models.Fichaje)
        .filter(models.Fichaje.user_id == usuario.id)
        .order_by(models.Fichaje.timestamp.desc())
        .first()
    )
    if ultimo and (ultimo.tipo or "").lower() == tipo_norm:
        raise ValueError(f"❌ Ya existe un fichaje de tipo '{tipo_norm}' justo antes.")

    # Salida requiere entrada previa
    if tipo_norm == "salida" and (not ultimo or (ultimo.tipo or "").lower() != "entrada"):
        raise ValueError("❌ No puedes fichar salida sin una entrada previa.")

    hash_val = generar_hash_fichaje(usuario.email, tipo_norm, ahora.isoformat())
    fichaje = models.Fichaje(tipo=tipo_norm, timestamp=ahora, hash=hash_val, usuario=usuario)
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
        }
        for f in fichajes
    ]


# ========================
#  Solicitudes manuales
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

    fichajes_usuario = (
        db.query(models.Fichaje)
        .filter(models.Fichaje.user_id == s.usuario.id)
        .order_by(models.Fichaje.timestamp)
        .all()
    )
    if s.tipo == "salida":
        for f in reversed(fichajes_usuario):
            if (f.tipo or "").lower() == "entrada":
                f_ts = _ensure_aware(f.timestamp, TZ_MADRID)
                if ts < f_ts:
                    raise ValueError("❌ La hora de salida no puede ser anterior a la entrada previa.")
                break
    if s.tipo == "entrada":
        for f in reversed(fichajes_usuario):
            if (f.tipo or "").lower() == "salida":
                f_ts = _ensure_aware(f.timestamp, TZ_MADRID)
                if ts < f_ts:
                    raise ValueError("❌ La hora de entrada no puede ser anterior a la salida previa.")
                break

    hash_val = generar_hash_fichaje(s.usuario.email, s.tipo, ts.isoformat())
    fichaje = models.Fichaje(
        tipo=(s.tipo or "").lower(),
        timestamp=ts,
        hash=hash_val,
        usuario=s.usuario,
        is_manual=True,
        motivo=s.motivo,
    )
    db.add(fichaje)

    s.estado = "aprobada"
    s.gestionado_por_id = admin.id if admin else None
    s.gestionado_en = datetime.now(pytz.UTC)
    s.ip_origen = ip

    log_evento(db, s.usuario, "fichaje manual aprobado", f"{ts.strftime('%d/%m/%Y %H:%M:%S')}|{s.motivo}")

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

    s.estado = "rechazada"
    s.motivo_rechazo = motivo if motivo else None
    s.gestionado_por_id = admin.id if admin else None
    s.gestionado_en = datetime.now(pytz.UTC)
    s.ip_origen = ip

    log_evento(db, s.usuario, "fichaje manual rechazado", s.motivo)

    db.commit()
    db.refresh(s)
    return s


# ========================
#  Logs (para LogsTab.jsx)
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
            "motivo": (getattr(f, "motivo", "") or "").strip() if getattr(f, "is_manual", False) else ""
        })
    return resultado


# ===================================================
#  Resumen Fichajes (con ausencias integradas)
# ===================================================
def _merge_intervalos(intervalos):
    if not intervalos:
        return []
    intervalos = sorted(intervalos, key=lambda x: x[0])
    res = [intervalos[0]]
    for s, e in intervalos[1:]:
        ls, le = res[-1]
        if s <= le:
            res[-1] = (ls, max(le, e))
        else:
            res.append((s, e))
    return res


def _sumar_union_intervalos(intervalos):
    if not intervalos:
        return 0
    merged = _merge_intervalos(intervalos)
    total = 0
    for s, e in merged:
        s = _ensure_aware(s, TZ_MADRID)
        e = _ensure_aware(e, TZ_MADRID)
        total += int((e - s).total_seconds())
    return total


def _huecos_del_dia(intervalos_trabajo, dia_dt: date, tz=TZ_MADRID):
    ini = _ensure_aware(datetime.combine(dia_dt, _time.min), tz)
    fin = _ensure_aware(datetime.combine(dia_dt, _time.max), tz)
    ocupados = _merge_intervalos(intervalos_trabajo)
    huecos, cursor = [], ini
    for s, e in ocupados:
        s = _ensure_aware(s, tz)
        e = _ensure_aware(e, tz)
        if s > cursor:
            huecos.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < fin:
        huecos.append((cursor, fin))
    return huecos


def _interseccion_seg(a_ini, a_fin, b_ini, b_fin, tz=TZ_MADRID) -> int:
    a_ini = _ensure_aware(a_ini, tz)
    a_fin = _ensure_aware(a_fin, tz)
    b_ini = _ensure_aware(b_ini, tz)
    b_fin = _ensure_aware(b_fin, tz)
    ini = max(a_ini, b_ini)
    fin = min(a_fin, b_fin)
    if fin <= ini:
        return 0
    return int((fin - ini).total_seconds())


def _tramo_ausencia_en_dia(a: Ausencia, dia_dt: date, tz=TZ_MADRID):
    if a.parcial:
        if dia_dt == a.fecha_inicio and a.hora_inicio is not None:
            ini = _ensure_aware(datetime.combine(dia_dt, a.hora_inicio), tz)
        else:
            ini = _ensure_aware(datetime.combine(dia_dt, _time.min), tz)
        if dia_dt == a.fecha_fin and a.hora_fin is not None:
            fin = _ensure_aware(datetime.combine(dia_dt, a.hora_fin), tz)
        else:
            fin = _ensure_aware(datetime.combine(dia_dt, _time.max), tz)
    else:
        ini = _ensure_aware(datetime.combine(dia_dt, _time.min), tz)
        fin = _ensure_aware(datetime.combine(dia_dt, _time.max), tz)
    return ini, fin


def resumen_fichajes_usuario(db: Session, usuario: models.User):
    fichajes = (
        db.query(models.Fichaje)
        .filter(models.Fichaje.user_id == usuario.id, models.Fichaje.timestamp != None)
        .order_by(models.Fichaje.timestamp.asc())
        .all()
    )

    aus_aprob = db.query(Ausencia).filter(
        Ausencia.usuario_email == usuario.email,
        Ausencia.estado == "APROBADA"
    ).all()

    por_dia = defaultdict(list)
    fichajes_futuros = []
    turno_abierto = None

    now_mad = datetime.now(TZ_MADRID)
    for f in fichajes:
        try:
            ts_local = _ensure_aware(f.timestamp, TZ_MADRID)
            if ts_local > now_mad:
                fichajes_futuros.append({
                    "tipo": f.tipo,
                    "timestamp": _safe_iso(f.timestamp),
                    "is_manual": getattr(f, "is_manual", False)
                })
            dia = ts_local.date().isoformat()
            por_dia[dia].append(f)
        except Exception:
            continue

    for a in aus_aprob:
        d = a.fecha_inicio
        while d <= a.fecha_fin:
            _ = por_dia[d.isoformat()]
            d += timedelta(days=1)

    resumen = {}
    for dia, lista in sorted(por_dia.items()):
        bloques = []
        pendiente = None
        total_segundos = 0

        for f in sorted(lista, key=lambda x: x.timestamp):
            try:
                ts = _ensure_aware(f.timestamp, TZ_MADRID)
                if (f.tipo or "").lower() == "entrada":
                    if pendiente:
                        bloques.append({
                            "entrada": {"timestamp": _safe_iso(pendiente.timestamp), "is_manual": getattr(pendiente, "is_manual", False)},
                            "salida": None,
                            "duracion": None,
                            "anomalia": "Entrada sin salida",
                        })
                    pendiente = f
                elif (f.tipo or "").lower() == "salida":
                    if pendiente:
                        t1 = _ensure_aware(pendiente.timestamp, TZ_MADRID)
                        t2 = ts
                        dur = (t2 - t1).total_seconds()
                        bloques.append({
                            "entrada": {"timestamp": _safe_iso(pendiente.timestamp), "is_manual": getattr(pendiente, "is_manual", False)},
                            "salida": {"timestamp": _safe_iso(f.timestamp), "is_manual": getattr(f, "is_manual", False)},
                            "duracion": int(dur),
                            "anomalia": None if dur >= 0 else "Duración negativa",
                        })
                        if dur > 0:
                            total_segundos += dur
                        pendiente = None
                    else:
                        bloques.append({
                            "entrada": None,
                            "salida": {"timestamp": _safe_iso(f.timestamp), "is_manual": getattr(f, "is_manual", False)},
                            "duracion": None,
                            "anomalia": "Salida sin entrada",
                        })
            except Exception:
                continue

        if pendiente:
            bloques.append({
                "entrada": {"timestamp": _safe_iso(pendiente.timestamp), "is_manual": getattr(pendiente, "is_manual", False)},
                "salida": None,
                "duracion": None,
                "anomalia": "Aún sin salida",
            })
            turno_abierto = {
                "desde": _safe_iso(pendiente.timestamp),
                "is_manual": getattr(pendiente, "is_manual", False)
            }

        dia_dt = datetime.strptime(dia, "%Y-%m-%d").date()

        intervalos_trabajo = []
        for b in bloques:
            if b.get("entrada") and b.get("salida") and b.get("duracion"):
                ini = _ensure_aware(datetime.fromisoformat(b["entrada"]["timestamp"]), TZ_MADRID)
                fin = _ensure_aware(datetime.fromisoformat(b["salida"]["timestamp"]), TZ_MADRID)
                intervalos_trabajo.append((ini, fin))
        intervalos_trabajo = _merge_intervalos(intervalos_trabajo)
        huecos = _huecos_del_dia(intervalos_trabajo, dia_dt, TZ_MADRID)

        aus_dia = [a for a in aus_aprob if a.fecha_fin >= dia_dt and a.fecha_inicio <= dia_dt]

        tramos_retribuibles = []
        existe_retribuida_dia_completo = False

        for a in aus_dia:
            a_ini, a_fin = _tramo_ausencia_en_dia(a, dia_dt, TZ_MADRID)
            if a.retribuida:
                for h_ini, h_fin in huecos:
                    ini = max(_ensure_aware(a_ini), _ensure_aware(h_ini))
                    fin = min(_ensure_aware(a_fin), _ensure_aware(h_fin))
                    if fin > ini:
                        tramos_retribuibles.append((ini, fin))
                if not a.parcial:
                    existe_retribuida_dia_completo = True

            bloques.append({
                "entrada": None,
                "salida": None,
                "duracion": 0,
                "anomalia": None,
                "ausencia": True,
                "tipo_ausencia": a.tipo,
                "subtipo": a.subtipo,
                "retribuida": bool(a.retribuida),
                "parcial": bool(a.parcial),
            })

        aus_retrib_seg = _sumar_union_intervalos(tramos_retribuibles)

        objetivo = int(HORAS_JORNADA_COMPLETA * 3600)
        if existe_retribuida_dia_completo:
            falta_para_jornada = max(0, objetivo - int(total_segundos + aus_retrib_seg))
            aus_retrib_seg += falta_para_jornada

        resumen[dia] = {
            "total": int(total_segundos),
            "bloques": bloques,
            "ausencias_retribuidas": int(aus_retrib_seg),
            "total_computado": int(total_segundos) + int(aus_retrib_seg)
        }

    return {
        "resumen": resumen,
        "_meta": {
            "turno_abierto": turno_abierto,
            "fichajes_futuros": fichajes_futuros
        }
    }


# ========================
#  Resumen Semana
# ========================
def resumen_semana_usuario(db: Session, usuario: models.User):
    data = resumen_fichajes_usuario(db, usuario)
    resumen = data["resumen"] if isinstance(data, dict) and "resumen" in data else data

    hoy = datetime.now(TZ_MADRID).date()
    lunes = hoy - timedelta(days=hoy.weekday())
    total_seg = 0

    for i in range(7):
        dia = (lunes + timedelta(days=i)).isoformat()
        day = resumen.get(dia, {}) or {}
        total_seg += int(day.get("total_computado", day.get("total", 0)))

    horas = total_seg // 3600
    minutos = (total_seg % 3600) // 60
    excedido = total_seg > 40 * 3600

    return {
        "inicio_semana": lunes.isoformat(),
        "total_segundos": total_seg,
        "horas": horas,
        "minutos": minutos,
        "excedido": excedido,
    }


# ========================
#  Admin usuarios
# ========================
def editar_usuario(db: Session, usuario_id: int, email: str, role: str):
    usuario = db.query(models.User).filter(models.User.id == usuario_id).first()
    if not usuario:
        raise Exception("Usuario no encontrado")
    usuario.email = email
    usuario.role = role
    db.commit()
    db.refresh(usuario)
    return usuario


def eliminar_usuario(db: Session, usuario_id: int):
    usuario = db.query(models.User).filter(models.User.id == usuario_id).first()
    if not usuario:
        raise Exception("Usuario no encontrado")
    db.delete(usuario)
    db.commit()
    return {"ok": True}


def restablecer_password(db: Session, usuario_id: int, nueva_password: str):
    from app.auth import hashear_password
    usuario = db.query(models.User).filter(models.User.id == usuario_id).first()
    if not usuario:
        raise Exception("Usuario no encontrado")
    usuario.hashed_password = hashear_password(nueva_password)
    db.commit()
    return {"ok": True}


# ========================
#  Ausencias — validaciones
# ========================
def _validar_rango_fechas(fecha_inicio: date, fecha_fin: date):
    if fecha_inicio > fecha_fin:
        raise ValueError("❌ La fecha de inicio no puede ser posterior a la fecha de fin.")


def _validar_parcial_horas(parcial: bool, hora_inicio: Optional[_time], hora_fin: Optional[_time]):
    if not parcial:
        return
    if hora_inicio is None or hora_fin is None:
        raise ValueError("❌ Ausencia parcial requiere hora_inicio y hora_fin.")
    if datetime.combine(date.today(), hora_inicio) >= datetime.combine(date.today(), hora_fin):
        raise ValueError("❌ En ausencia parcial, hora_inicio debe ser anterior a hora_fin.")


def _solapa(a_ini: date, a_fin: date, b_ini: date, b_fin: date) -> bool:
    return not (a_fin < b_ini or b_fin < a_ini)


def _existe_solapamiento(db: Session, usuario_email: str, fecha_inicio: date, fecha_fin: date, excluir_id: Optional[int] = None) -> bool:
    q = db.query(Ausencia).filter(
        Ausencia.usuario_email == usuario_email,
        Ausencia.estado.in_(["PENDIENTE", "APROBADA"])
    )
    if excluir_id:
        q = q.filter(Ausencia.id != excluir_id)
    for a in q.all():
        if _solapa(fecha_inicio, fecha_fin, a.fecha_inicio, a.fecha_fin):
            return True
    return False


# ========================
#  Convenios / Saldos — Helpers
# ========================
def _festivos_set_para_rango(db: Session, user_id: int, inicio: date, fin: date) -> set[date]:
    try:
        rows = obtener_festivos_por_usuario_en_rango(db, user_id, inicio, fin)
        return {r["date"] for r in rows if r.get("date")}
    except Exception:
        return set()


def _contar_dias_en_rango(inicio: date, fin: date, computo: ComputoDiasEnum, festivos: set[date]) -> float:
    if inicio > fin:
        return 0.0
    if computo == ComputoDiasEnum.NATURALES:
        return float((fin - inicio).days + 1)
    dias = 0
    cur = inicio
    while cur <= fin:
        if cur.weekday() < 5 and cur not in festivos:
            dias += 1
        cur += timedelta(days=1)
    return float(dias)


def obtener_regla_vigente(db: Session, usuario_id: int, tipo: str, fecha_referencia: date) -> ReglaAusencia | None:
    uc = (
        db.query(UsuarioConvenio)
        .filter(
            UsuarioConvenio.usuario_id == usuario_id,
            UsuarioConvenio.vigente_desde <= fecha_referencia,
            or_(UsuarioConvenio.vigente_hasta == None, UsuarioConvenio.vigente_hasta >= fecha_referencia),
        )
        .order_by(UsuarioConvenio.vigente_desde.desc())
        .first()
    )
    if not uc:
        return None

    tipo_upper = (tipo or "").upper()
    if tipo_upper not in TipoAusenciaEnum.__members__:
        return None

    regla = (
        db.query(ReglaAusencia)
        .filter(ReglaAusencia.convenio_id == uc.convenio_id, ReglaAusencia.tipo == TipoAusenciaEnum[tipo_upper])
        .first()
    )
    return regla


def obtener_o_crear_saldo(db: Session, usuario_id: int, tipo: str, anio: int) -> SaldoAusencia:
    tipo_upper = (tipo or "").upper()
    if tipo_upper not in TipoAusenciaEnum.__members__:
        raise ValueError("Tipo de ausencia no soportado para saldos.")
    saldo = (
        db.query(SaldoAusencia)
        .filter(SaldoAusencia.usuario_id == usuario_id, SaldoAusencia.tipo == TipoAusenciaEnum[tipo_upper], SaldoAusencia.anio == anio)
        .first()
    )
    if saldo:
        return saldo
    saldo = SaldoAusencia(
        usuario_id=usuario_id,
        tipo=TipoAusenciaEnum[tipo_upper],
        anio=anio,
        asignado=0,
        arrastre=0,
        gastado=0,
    )
    db.add(saldo)
    db.flush()
    return saldo


def registrar_movimiento(db: Session, saldo: SaldoAusencia, delta: float, motivo: MotivoMovimientoEnum, referencia: str | None = None):
    """
    - Registra en ledger.
    - Solo toca 'gastado' en APROBACION (delta<0) o REVERSO (delta>0).
    """
    mov = MovimientoSaldoAusencia(
        saldo_id=saldo.id,
        delta=delta,
        motivo=motivo,
        referencia=(referencia or None)[:50] if referencia else None,
    )
    db.add(mov)

    if motivo in (MotivoMovimientoEnum.APROBACION, MotivoMovimientoEnum.REVERSO):
        if delta < 0:
            saldo.gastado = (saldo.gastado or 0) + abs(delta)
        elif delta > 0:
            saldo.gastado = max(0, (saldo.gastado or 0) - delta)

    db.add(saldo)


def ajustar_saldo(
    db: Session,
    usuario_id: int,
    tipo: str,
    anio: int,
    delta: float,
    comentario: str | None = None,
) -> dict:
    """
    Ajusta el 'asignado' (no 'gastado'):
    - delta>0 suma asignado; delta<0 resta asignado
    - No permite dejar disponible < 0
    """
    tipo_upper = (tipo or "").upper()
    saldo = obtener_o_crear_saldo(db, usuario_id, tipo_upper, anio)

    asignado = float(saldo.asignado or 0)
    arrastre = float(saldo.arrastre or 0)
    gastado = float(saldo.gastado or 0)

    nuevo_asignado = asignado + float(delta)
    if nuevo_asignado < 0:
        raise ValueError("El ajuste dejaría el asignado por debajo de 0.")

    disponible_despues = (nuevo_asignado + arrastre) - gastado
    if disponible_despues < 0:
        raise ValueError("El ajuste dejaría el disponible en negativo.")

    saldo.asignado = nuevo_asignado
    db.add(saldo)

    registrar_movimiento(
        db=db,
        saldo=saldo,
        delta=float(delta),
        motivo=MotivoMovimientoEnum.AJUSTE,
        referencia=(comentario or "")[:50] or "ajuste",
    )

    db.commit()
    db.refresh(saldo)

    return {
        "usuario_id": usuario_id,
        "tipo": tipo_upper,
        "anio": anio,
        "asignado": float(saldo.asignado or 0),
        "arrastre": arrastre,
        "gastado": gastado,
        "disponible": float((saldo.asignado or 0) + arrastre - gastado),
    }


# ========================
#  Ausencias — CRUD
# ========================
def _dt_madrid(d: date, t: Optional[_time], inicio: bool, tz=TZ_MADRID) -> datetime:
    if t is None:
        naive = datetime.combine(d, _time.min) if inicio else datetime.combine(d + timedelta(days=1), _time.min)
    else:
        naive = datetime.combine(d, t)
    return tz.localize(naive)


def _calc_duracion_ausencia_seg(a: Ausencia) -> int:
    try:
        if not a.parcial:
            ini = _dt_madrid(a.fecha_inicio, None, True)
            fin = _dt_madrid(a.fecha_fin, None, False)
        else:
            ini = _dt_madrid(a.fecha_inicio, a.hora_inicio, True)
            fin = _dt_madrid(a.fecha_fin, a.hora_fin, False)
        seg = int((fin - ini).total_seconds())
        return max(0, seg)
    except Exception:
        return 0


def _attach_duracion(a: Ausencia):
    try:
        setattr(a, "duracion_segundos", _calc_duracion_ausencia_seg(a))
    except Exception:
        setattr(a, "duracion_segundos", 0)
    return a


def crear_ausencia(db: Session, data: AusenciaCreate, creador_email: str) -> Ausencia:
    _validar_rango_fechas(data.fecha_inicio, data.fecha_fin)
    _validar_parcial_horas(data.parcial, data.hora_inicio, data.hora_fin)

    if _existe_solapamiento(db, data.usuario_email, data.fecha_inicio, data.fecha_fin):
        raise ValueError("❌ Ya existe una ausencia solapada (pendiente o aprobada) para ese periodo.")

    ausencia = Ausencia(
        usuario_email=data.usuario_email,
        tipo=data.tipo,
        subtipo=data.subtipo,
        fecha_inicio=data.fecha_inicio,
        hora_inicio=data.hora_inicio,
        fecha_fin=data.fecha_fin,
        hora_fin=data.hora_fin,
        parcial=data.parcial,
        retribuida=data.retribuida,
        estado="PENDIENTE",
        motivo=data.motivo,
        creada_por=creador_email,
    )
    db.add(ausencia)
    db.flush()

    db.add(LogAuditoria(
        accion="AUSENCIA_CREADA",
        detalle=f"{creador_email} creó ausencia #{ausencia.id} para {data.usuario_email} ({data.tipo})",
        motivo=data.motivo,
        user_id=None
    ))
    db.commit()
    db.refresh(ausencia)
    return _attach_duracion(ausencia)


def listar_ausencias(
    db: Session,
    usuario_email: str | None = None,
    estado: str | None = None,
    tipo: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
):
    q = db.query(Ausencia)
    if usuario_email:
        q = q.filter(Ausencia.usuario_email == usuario_email)
    if estado:
        q = q.filter(Ausencia.estado == estado)
    if tipo:
        q = q.filter(Ausencia.tipo == tipo)
    if desde:
        q = q.filter(Ausencia.fecha_fin >= desde)
    if hasta:
        q = q.filter(Ausencia.fecha_inicio <= hasta)
    items = q.order_by(Ausencia.fecha_inicio.desc(), Ausencia.id.desc()).all()
    for a in items:
        _attach_duracion(a)
    return items


def actualizar_ausencia(db: Session, ausencia_id: int, data: AusenciaUpdate) -> Ausencia | None:
    ausencia = db.get(Ausencia, ausencia_id)
    if not ausencia:
        return None

    payload = ausencia.__dict__.copy()
    payload.update({k: v for k, v in data.dict(exclude_unset=True).items()})

    _validar_rango_fechas(payload["fecha_inicio"], payload["fecha_fin"])
    _validar_parcial_horas(payload["parcial"], payload.get("hora_inicio"), payload.get("hora_fin"))

    if _existe_solapamiento(db, ausencia.usuario_email, payload["fecha_inicio"], payload["fecha_fin"], excluir_id=ausencia_id):
        raise ValueError("❌ El nuevo rango se solapa con otra ausencia (pendiente o aprobada).")

    for campo, valor in data.dict(exclude_unset=True).items():
        setattr(ausencia, campo, valor)

    db.add(ausencia)
    db.add(LogAuditoria(
        accion="AUSENCIA_EDITADA",
        detalle=f"Ausencia #{ausencia_id} editada",
        motivo=getattr(data, "motivo", None),
        user_id=None
    ))
    db.commit()
    db.refresh(ausencia)
    return _attach_duracion(ausencia)


def calcular_dias_solicitud_convenio(
    db: Session,
    usuario: models.User,
    tipo: str,
    fecha_inicio: date,
    fecha_fin: date,
    parcial: bool,
    hora_inicio: Optional[_time],
    hora_fin: Optional[_time],
) -> float:
    regla = obtener_regla_vigente(db, usuario.id, tipo, fecha_inicio)
    if not regla:
        return 0.0

    if parcial and fecha_inicio == fecha_fin:
        if regla.permite_mediodia:
            return 0.5
        # si no permite, contar según cómputo
    festivos = _festivos_set_para_rango(db, usuario.id, fecha_inicio, fecha_fin)
    return max(0.0, _contar_dias_en_rango(fecha_inicio, fecha_fin, regla.computo, festivos))


def aprobar_ausencia(db: Session, ausencia_id: int, admin_email: str) -> Ausencia | None:
    ausencia = db.get(Ausencia, ausencia_id)
    if not ausencia:
        return None

    _validar_rango_fechas(ausencia.fecha_inicio, ausencia.fecha_fin)
    _validar_parcial_horas(ausencia.parcial, ausencia.hora_inicio, ausencia.hora_fin)

    if _existe_solapamiento(db, ausencia.usuario_email, ausencia.fecha_inicio, ausencia.fecha_fin, excluir_id=ausencia.id):
        raise ValueError("❌ No se puede aprobar: se solapa con otra ausencia pendiente/aprobada.")

    tipo_upper = (ausencia.tipo or "").upper()
    consume_saldo = tipo_upper in {"VACACIONES", "ASUNTOS_PROPIOS"}

    if consume_saldo:
        usuario = obtener_usuario_por_email(db, ausencia.usuario_email)
        if not usuario:
            raise ValueError("Usuario no encontrado para aplicar saldo.")

        dias_consumo = calcular_dias_solicitud_convenio(
            db=db,
            usuario=usuario,
            tipo=tipo_upper,
            fecha_inicio=ausencia.fecha_inicio,
            fecha_fin=ausencia.fecha_fin,
            parcial=ausencia.parcial,
            hora_inicio=ausencia.hora_inicio,
            hora_fin=ausencia.hora_fin,
        )

        if dias_consumo > 0:
            anio = ausencia.fecha_inicio.year
            saldo = obtener_o_crear_saldo(db, usuario.id, tipo_upper, anio)
            disponible = float((saldo.asignado or 0) + (saldo.arrastre or 0) - (saldo.gastado or 0))
            if dias_consumo > disponible:
                raise ValueError(f"❌ No hay saldo suficiente. Necesitas {dias_consumo:.2f} y te quedan {disponible:.2f} días.")

            registrar_movimiento(
                db=db,
                saldo=saldo,
                delta=-dias_consumo,
                motivo=MotivoMovimientoEnum.APROBACION,
                referencia=f"ausencia:{ausencia.id}",
            )

    ausencia.estado = "APROBADA"
    ausencia.aprobada_por = admin_email
    db.add(ausencia)
    db.add(LogAuditoria(
        accion="AUSENCIA_APROBADA",
        detalle=f"{admin_email} aprobó ausencia #{ausencia_id}",
        motivo=ausencia.motivo,
        user_id=None
    ))

    db.commit()
    db.refresh(ausencia)
    return _attach_duracion(ausencia)


def rechazar_ausencia(db: Session, ausencia_id: int, admin_email: str) -> Ausencia | None:
    ausencia = db.get(Ausencia, ausencia_id)
    if not ausencia:
        return None
    ausencia.estado = "RECHAZADA"
    ausencia.aprobada_por = None
    db.add(ausencia)
    db.add(LogAuditoria(
        accion="AUSENCIA_RECHAZADA",
        detalle=f"{admin_email} rechazó ausencia #{ausencia_id}",
        motivo=ausencia.motivo,
        user_id=None
    ))
    db.commit()
    db.refresh(ausencia)
    return _attach_duracion(ausencia)


def obtener_ausencias_aprobadas_en_dia(db: Session, usuario_email: str, d: date):
    return db.query(Ausencia).filter(
        Ausencia.usuario_email == usuario_email,
        Ausencia.estado == "APROBADA",
        Ausencia.fecha_fin >= d,
        Ausencia.fecha_inicio <= d
    ).all()


# ===================================================
#  FESTIVOS + FEED DE CALENDARIO (adaptado a tu schema)
# ===================================================
def _get_user_location_ids(db: Session, user_id: int) -> tuple[Optional[int], Optional[int]]:
    """
    Devuelve (region_id, locality_id) de la última ubicación conocida del usuario.
    """
    ul = (
        db.query(UserLocation)
        .filter(UserLocation.user_id == user_id)
        .order_by(UserLocation.created_at.desc(), UserLocation.id.desc())
        .first()
    )
    if not ul:
        return None, None
    return ul.region_id, ul.locality_id


def obtener_festivos_por_usuario_en_rango(db: Session, user_id: int, start: date, end: date):
    """
    Usa CalendarMark(fecha, nombre, tipo, ambito, region_id, locality_id)
    y UserLocation(region_id, locality_id).

    Devuelve una lista de dicts con llaves compatibles con el resto del código:
      { "date": fecha, "name": nombre, "scope": 'national'|'region'|'local' }
    """
    region_id, locality_id = _get_user_location_ids(db, user_id)

    q = db.query(CalendarMark).filter(
        CalendarMark.tipo == "FESTIVO",
        CalendarMark.fecha >= start,
        CalendarMark.fecha <= end,
        CalendarMark.country_code == "ES",
    )

    # Siempre incluir NACIONAL
    # Además, si hay region_id/locality_id y el ambito/ids coinciden, incluirlos.
    marks = q.all()

    rows: List[Dict] = []
    for m in marks:
        amb = (m.ambito or "").upper()
        include = False
        scope = None

        if amb == "NACIONAL":
            include = True
            scope = "national"
        elif amb == "AUTONOMICO":
            if region_id is not None and m.region_id == region_id:
                include = True
                scope = "region"
        elif amb == "LOCAL":
            if locality_id is not None and m.locality_id == locality_id:
                include = True
                scope = "local"

        if include:
            rows.append({
                "date": m.fecha,
                "name": m.nombre,
                "scope": scope,
            })

    # De-duplicate por (date, scope)
    seen = set()
    dedup = []
    for r in rows:
        key = (r["date"], r["scope"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(r)

    return dedup


def obtener_ausencias_usuario_en_rango(db: Session, usuario_email: str, start: date, end: date):
    return (
        db.query(Ausencia)
        .filter(
            Ausencia.usuario_email == usuario_email,
            Ausencia.fecha_inicio <= end,
            Ausencia.fecha_fin >= start
        )
        .order_by(Ausencia.fecha_inicio.asc())
        .all()
    )


def _daterange(d1: date, d2: date):
    cur = d1
    while cur <= d2:
        yield cur
        cur += timedelta(days=1)


def obtener_eventos_calendario(db: Session, user_id: int, start: date, end: date) -> List[Dict]:
    user = obtener_usuario_por_id(db, user_id)
    if not user:
        return []

    eventos: List[Dict] = []

    festivos = obtener_festivos_por_usuario_en_rango(db, user_id, start, end)
    seen = set()
    for f in festivos:
        d = f.get("date")
        n = f.get("name")
        s = f.get("scope")
        if not d or not n:
            continue
        key = (d, s)
        if key in seen:
            continue
        seen.add(key)
        eventos.append({
            "fecha": d,
            "titulo": n,
            "type": "FESTIVO",
            "estado": None,
            "scope": s,
        })

    ausencias = obtener_ausencias_usuario_en_rango(db, user.email, start, end)
    for a in ausencias:
        tipo_upper = (a.tipo or "").upper()
        tipo_norm = "AUSENCIA"
        if tipo_upper == "VACACIONES":
            tipo_norm = "VACACIONES"
        elif tipo_upper == "CITA_MEDICA":
            tipo_norm = "CITA_MEDICA"

        ini = max(a.fecha_inicio, start)
        fin = min(a.fecha_fin, end)
        for d in _daterange(ini, fin):
            eventos.append({
                "fecha": d,
                "titulo": a.tipo,
                "type": tipo_norm,
                "estado": a.estado
            })

    eventos.sort(key=lambda e: e["fecha"])
    return eventos


# ========================
#  Previsualización (formulario)
# ========================
def previsualizar_consumo_ausencia(
    db: Session, usuario_email: str, tipo: str,
    fecha_inicio: date, fecha_fin: date,
    parcial: bool, hora_inicio: Optional[_time], hora_fin: Optional[_time]
) -> dict:
    usuario = obtener_usuario_por_email(db, usuario_email)
    if not usuario:
        raise ValueError("Usuario no encontrado")

    tipo_upper = (tipo or "").upper()
    dias = calcular_dias_solicitud_convenio(db, usuario, tipo_upper, fecha_inicio, fecha_fin, parcial, hora_inicio, hora_fin)
    anio = fecha_inicio.year

    disponible = None
    if tipo_upper in {"VACACIONES", "ASUNTOS_PROPIOS"}:
        saldo = obtener_o_crear_saldo(db, usuario.id, tipo_upper, anio)
        disponible = float((saldo.asignado or 0) + (saldo.arrastre or 0) - (saldo.gastado or 0))

    return {
        "dias_calculados": float(dias),
        "disponible_actual": float(disponible) if disponible is not None else None,
        "disponible_si_aprueba": float(disponible - dias) if disponible is not None else None,
        "anio": anio,
    }

