from __future__ import annotations

from datetime import datetime, timedelta, date, time as _time
from collections import defaultdict
from typing import Optional, List, Dict

import pytz
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text
from sqlalchemy.exc import SQLAlchemyError

from app import models
from app.utils import generar_hash_fichaje, log_evento
from app.schemas_solicitudes import SolicitudManualCreate, SolicitudFiltro
from app.config import HORAS_JORNADA_COMPLETA
from app.models import Ausencia, LogAuditoria
from app.schemas_ausencias import AusenciaCreate, AusenciaUpdate
import re

# ========================
#  Zona horaria (única)
# ========================
TZ_MADRID = pytz.timezone("Europe/Madrid")
_VALID_TIPOS = {"entrada", "salida"}


# ========================
#  Helpers generales
# ========================
def _ensure_aware(dt: Optional[datetime], tz=TZ_MADRID) -> Optional[datetime]:
    """Devuelve dt con tz; si era naive, lo localiza; si tenía otra tz, la convierte."""
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

    # --- Bloqueo por ausencias/vacaciones aprobadas ---
    aus = _ausencias_aprobadas_en_instante(db, usuario.email, ahora)
    for a in aus:
        # Bloquear fichajes en vacaciones retribuidas de día completo
        if (a.tipo or "").upper() == "VACACIONES" and not a.parcial and a.retribuida:
            raise ValueError("❌ No puedes fichar: tienes VACACIONES retribuidas aprobadas hoy.")
        # Otros tipos retribuidos de día completo
        if a.retribuida and not a.parcial and (a.tipo or "").upper() != "VACACIONES":
            raise ValueError(f"❌ No puedes fichar: existe una ausencia retribuida aprobada hoy ({a.tipo}).")
        # Parcial: bloquear si el instante cae dentro del tramo parcial
        if a.parcial and _instante_en_parcial(a, ahora):
            rango = []
            if a.hora_inicio:
                rango.append(a.hora_inicio.strftime("%H:%M"))
            if a.hora_fin:
                rango.append(a.hora_fin.strftime("%H:%M"))
            detalle = " - ".join(rango) if rango else "tramo parcial"
            raise ValueError(f"❌ No puedes fichar dentro de una ausencia parcial aprobada ({detalle}).")

    # VALIDACIÓN: no permitir dos entradas o dos salidas consecutivas
    ultimo = (
        db.query(models.Fichaje)
        .filter(models.Fichaje.user_id == usuario.id)
        .order_by(models.Fichaje.timestamp.desc())
        .first()
    )
    if ultimo and (ultimo.tipo or "").lower() == tipo_norm:
        raise ValueError(f"❌ Ya existe un fichaje de tipo '{tipo_norm}' justo antes. No se permiten fichajes consecutivos del mismo tipo.")

    # VALIDACIÓN: si tipo == salida, debe haber entrada previa
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
#  Solicitudes Manuales
# ========================
def _parse_fecha_hora(fecha: str, hora: str, tz=TZ_MADRID) -> datetime:
    """
    Intenta parsear fecha/hora en formatos dd/mm/YYYY y YYYY-mm-dd.
    Asegura segundos en la hora y devuelve SIEMPRE tz-aware.
    """
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

    # VALIDACIÓN: impedir solicitudes futuras
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


# --- Listado avanzado con filtros + paginación (server-side) ---
def listar_solicitudes_avanzado(
    db: Session,
    filtro: Optional[SolicitudFiltro] = None,
    solo_pendientes: bool = False,
):
    """
    Devuelve {items, total, page, per_page} aplicando filtros.
    """
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
            "fecha": models.SolicitudManual.timestamp,  # alias
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
        gp = getattr(s, "gestionado_por", None)  # puede no existir en el modelo actual
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


# --- Acciones con auditoría y logs ---
def aprobar_solicitud(db: Session, solicitud_id: int, admin: models.User, ip: Optional[str] = None):
    """
    Aprueba una solicitud creando el fichaje manual correspondiente,
    rellenando auditoría y registrando log.
    """
    s = db.query(models.SolicitudManual).filter(models.SolicitudManual.id == solicitud_id).first()
    if not s:
        raise ValueError("Solicitud no encontrada")
    if s.estado != "pendiente":
        raise ValueError("La solicitud ya fue gestionada")

    # Convertir siempre a datetime con zona horaria
    ts = _parse_fecha_hora(s.fecha, s.hora, TZ_MADRID)

    # Validaciones de coherencia
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

    # Crear fichaje manual
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

    # Auditoría en solicitud (si los campos existen, se persisten; si no, no rompen)
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
    """Devuelve huecos del día [00:00, 23:59:59.999...] en tz, descontando intervalos_trabajo."""
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
    """Intersección en segundos entre [a_ini, a_fin] y [b_ini, b_fin] (todo tz-aware)."""
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
    """Devuelve (ini_dt, fin_dt) de la ausencia acotada al día 'dia_dt', tz-aware."""
    if a.parcial:
        # Primer día: desde hora_inicio; último día: hasta hora_fin; intermedios: día completo
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

    # Cargamos todas las AUSENCIAS APROBADAS del usuario (una vez)
    aus_aprob = db.query(Ausencia).filter(
        Ausencia.usuario_email == usuario.email,
        Ausencia.estado == "APROBADA"
    ).all()

    por_dia = defaultdict(list)
    fichajes_futuros = []
    turno_abierto = None

    # Indexar fichajes por día
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
            continue  # fichaje corrupto

    # Asegurar que días con SOLO ausencias también aparezcan
    for a in aus_aprob:
        d = a.fecha_inicio
        while d <= a.fecha_fin:
            _ = por_dia[d.isoformat()]  # crea clave si no existe
            d += timedelta(days=1)

    resumen = {}
    for dia, lista in sorted(por_dia.items()):
        bloques = []
        pendiente = None
        total_segundos = 0

        # ---- intervalos de trabajo ----
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
                continue  # bloque corrupto, ignorar

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

        # ---- integrar AUSENCIAS del día (rellenando huecos, sin doble conteo) ----
        dia_dt = datetime.strptime(dia, "%Y-%m-%d").date()

        # Construir intervalos de trabajo del día para obtener huecos
        intervalos_trabajo = []
        for b in bloques:
            if b.get("entrada") and b.get("salida") and b.get("duracion"):
                ini = _ensure_aware(datetime.fromisoformat(b["entrada"]["timestamp"]), TZ_MADRID)
                fin = _ensure_aware(datetime.fromisoformat(b["salida"]["timestamp"]), TZ_MADRID)
                intervalos_trabajo.append((ini, fin))
        intervalos_trabajo = _merge_intervalos(intervalos_trabajo)
        huecos = _huecos_del_dia(intervalos_trabajo, dia_dt, TZ_MADRID)

        # Ausencias que afectan al día
        aus_dia = [a for a in aus_aprob if a.fecha_fin >= dia_dt and a.fecha_inicio <= dia_dt]

        # 3.1 Construir la UNIÓN de tramos retribuidos (intersecciones con huecos)
        tramos_retribuibles = []
        existe_retribuida_dia_completo = False  # p.ej. vacaciones completas

        for a in aus_dia:
            # tramo de ausencia acotado al día
            a_ini, a_fin = _tramo_ausencia_en_dia(a, dia_dt, TZ_MADRID)

            if a.retribuida:
                # Intersectar ausencia con cada hueco para evitar doble cómputo
                for h_ini, h_fin in huecos:
                    ini = max(_ensure_aware(a_ini), _ensure_aware(h_ini))
                    fin = min(_ensure_aware(a_fin), _ensure_aware(h_fin))
                    if fin > ini:
                        tramos_retribuibles.append((ini, fin))

                # Marcar si hay retribuida de día completo
                if not a.parcial:
                    existe_retribuida_dia_completo = True

            # Añadir bloque informativo a la UI (duración temporal, no suma)
            bloques.append({
                "entrada": None,
                "salida": None,
                "duracion": 0,  # si quieres, puedes recalcular por ausencia para UI
                "anomalia": None,
                "ausencia": True,
                "tipo_ausencia": a.tipo,
                "subtipo": a.subtipo,
                "retribuida": bool(a.retribuida),
                "parcial": bool(a.parcial),
            })

        # 3.2 Segundos retribuidos por la unión de tramos
        aus_retrib_seg = _sumar_union_intervalos(tramos_retribuibles)

        # 3.3 Relleno hasta jornada completa SOLO por el componente retribuido (no por trabajo real)
        objetivo = int(HORAS_JORNADA_COMPLETA * 3600)
        if existe_retribuida_dia_completo:
            falta_para_jornada = max(0, objetivo - int(total_segundos + aus_retrib_seg))
            aus_retrib_seg += falta_para_jornada  # rellena pero NUNCA supera jornada por la parte retribuida

        resumen[dia] = {
            "total": int(total_segundos),                       # solo fichajes reales
            "bloques": bloques,
            "ausencias_retribuidas": int(aus_retrib_seg),       # segundos por ausencias retribuidas (unión)
            "total_computado": int(total_segundos) + int(aus_retrib_seg)  # real + retribuidas
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
        # Usar total_computado si está; si no, caer en 'total'
        total_seg += int(day.get("total_computado", day.get("total", 0)))

    horas = total_seg // 3600
    minutos = (total_seg % 3600) // 60
    excedido = total_seg > 40 * 3600  # 40 h

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
#  Ausencias
# ========================
# === Helpers validación de rangos/solapes ===
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


# === Helpers de duración nominal (para no tocar rutas) ===
def _dt_madrid(d: date, t: Optional[_time], inicio: bool, tz=TZ_MADRID) -> datetime:
    """
    Convierte (date, time) a datetime tz-aware en Europe/Madrid.
    Día completo: inicio -> 00:00; fin -> 24:00 (día siguiente 00:00).
    """
    if t is None:
        naive = datetime.combine(d, _time.min) if inicio else datetime.combine(d + timedelta(days=1), _time.min)
    else:
        naive = datetime.combine(d, t)
    return tz.localize(naive)


def _calc_duracion_ausencia_seg(a: Ausencia) -> int:
    """Duración nominal: días completos inclusivos (no parcial) o tramo parcial hi→hf (soporta cruce de fecha)."""
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
    """Adjunta 'duracion_segundos' como atributo dinámico para que lo recoja el schema sin cambiar rutas."""
    try:
        setattr(a, "duracion_segundos", _calc_duracion_ausencia_seg(a))
    except Exception:
        setattr(a, "duracion_segundos", 0)
    return a


def crear_ausencia(db: Session, data: AusenciaCreate, creador_email: str) -> Ausencia:
    # Validaciones de coherencia
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
    db.flush()  # obtener id

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
    # Adjuntar duración a cada ítem sin tocar el modelo/DB
    for a in items:
        _attach_duracion(a)
    return items


def actualizar_ausencia(db: Session, ausencia_id: int, data: AusenciaUpdate) -> Ausencia | None:
    ausencia = db.query(Ausencia).get(ausencia_id)
    if not ausencia:
        return None

    payload = ausencia.__dict__.copy()
    payload.update({k: v for k, v in data.dict(exclude_unset=True).items()})

    # Validaciones tras aplicar cambios
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


def aprobar_ausencia(db: Session, ausencia_id: int, admin_email: str) -> Ausencia | None:
    ausencia = db.query(Ausencia).get(ausencia_id)
    if not ausencia:
        return None

    # Revalidar coherencia y solapes antes de aprobar
    _validar_rango_fechas(ausencia.fecha_inicio, ausencia.fecha_fin)
    _validar_parcial_horas(ausencia.parcial, ausencia.hora_inicio, ausencia.hora_fin)

    if _existe_solapamiento(db, ausencia.usuario_email, ausencia.fecha_inicio, ausencia.fecha_fin, excluir_id=ausencia.id):
        raise ValueError("❌ No se puede aprobar: se solapa con otra ausencia pendiente/aprobada.")

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
    ausencia = db.query(Ausencia).get(ausencia_id)
    if not ausencia:
        return None
    ausencia.estado = "RECHAZADA"
    ausencia.aprobada_por = None  # no se fija aprobador en un rechazo
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


# Helper para el cómputo diario (lo usaremos luego en exportadores/resúmenes)
def obtener_ausencias_aprobadas_en_dia(db: Session, usuario_email: str, d: date):
    return db.query(Ausencia).filter(
        Ausencia.usuario_email == usuario_email,
        Ausencia.estado == "APROBADA",
        Ausencia.fecha_fin >= d,
        Ausencia.fecha_inicio <= d
    ).all()


# ===================================================
#  FESTIVOS + FEED DE CALENDARIO
# ===================================================

# Formato completo típico: ES-XX-Nombre-INE5  (p.ej. ES-MD-Madrid-28079)
_LOCALITY_RE = re.compile(r'^ES-[A-Z]{2}-[^-]+-(\d{5})$')

def _derive_from_locality_code(db: Session, locality_code: str):
    l = (locality_code or "").strip()

    m = re.match(r'^ES-([A-Z]{2})-[^-]+-(\d{5})$', l)
    if m:
        reg = f"ES-{m.group(1)}"
        prov = f"{reg}-{m.group(2)[:2]}"
        return reg, prov

    if re.fullmatch(r"\d{5}", l):
        row = db.execute(
            text("""
                SELECT region_code, province_code
                FROM localities
                WHERE RIGHT(code, 5) = :ine
                LIMIT 1
            """),
            {"ine": l},
        ).mappings().first()
        if row:
            return row["region_code"], row["province_code"]

    return None, None


def _get_user_location_codes(db: Session, user_id: int):
    """
    Devuelve (region_code, province_code, locality_code).
    Importante: devolvemos locality_code TAL CUAL está en user_locations.local_code
    para poder filtrar festivos 'local' (calendar_marks.locality_code).
    """
    row = db.execute(text("""
        SELECT region_code, local_code
        FROM user_locations
        WHERE user_id = :uid
        ORDER BY created_at DESC NULLS LAST, id DESC
        LIMIT 1
    """), {"uid": user_id}).mappings().first()

    if not row:
        # Sin ubicación → solo festivos nacionales
        return "", "", ""

    r_code = (row.get("region_code") or "").strip()
    l_code = (row.get("local_code") or "").strip()
    # province_code no lo usas en tu dataset actual → devolver vacío
    return r_code, "", l_code


def _collapse_one_event_per_day(rows):
    """
    De varios festivos el mismo día, deja sólo 1 con prioridad:
    local > province > region > national
    """
    priority = {"local": 4, "province": 3, "region": 2, "national": 1}
    best_by_day = {}
    for r in rows:
        d = r.get("date") or r.get("fecha")
        s = r.get("scope")
        if not d or not s:
            continue
        cur = best_by_day.get(d)
        if cur is None or priority.get(s, 0) > priority.get(cur["scope"], 0):
            best_by_day[d] = r
    return [best_by_day[k] for k in sorted(best_by_day.keys())]


def obtener_festivos_por_usuario_en_rango(db: Session, user_id: int, start: date, end: date):
    r_code, p_code, l_code = _get_user_location_codes(db, user_id)

    params = {
        "start": start,      # tipos date
        "end": end,
        "r": r_code or "",
        "p": p_code or "",
        "l": l_code or "",
    }

    # NOTA: usamos SELECT :r, :p, :l (sin ::text) para evitar el error de sintaxis en psycopg/psycopg2
    sql = text("""
        WITH target(r, p, l) AS (SELECT :r, :p, :l)
        SELECT scope, mark, date, name, region_code, province_code, locality_code
        FROM calendar_marks, target
        WHERE mark = 'holiday'
          AND date BETWEEN :start AND :end
          AND (
                scope = 'national'
             OR (scope = 'region'   AND target.r <> '' AND region_code   = target.r)
             OR (scope = 'province' AND target.p <> '' AND province_code = target.p)
             OR (scope = 'local'    AND target.l <> '' AND locality_code = target.l)
          )
        ORDER BY date ASC, scope ASC
    """)

    try:
        rows = [dict(x) for x in db.execute(sql, params).mappings().all()]
    except SQLAlchemyError as e:
        # No tirar la API: log de depuración y devolver vacío
        print("[CALDEBUG error] festivos query:", e)
        return []

    # Defensa extra y deduplicación (por si hay espacios o mayúsculas en DB)
    out = []
    for r in rows:
        sc = (r.get("scope") or "").strip()
        if sc == "national":
            out.append(r)
        elif sc == "region" and params["r"] and (r.get("region_code") or "").strip() == params["r"]:
            out.append(r)
        elif sc == "province" and params["p"] and (r.get("province_code") or "").strip() == params["p"]:
            out.append(r)
        elif sc == "local" and params["l"] and (r.get("locality_code") or "").strip() == params["l"]:
            out.append(r)

    # Dedupe por (fecha, nombre, scope)
    vistos = set()
    dedup = []
    for r in out:
        k = (r.get("date"), (r.get("name") or "").strip(), (r.get("scope") or "").strip())
        if k in vistos:
            continue
        vistos.add(k)
        dedup.append(r)

    print(f"[CALDEBUG result] user_id={user_id} rows={len(dedup)} sample={[(x['date'], x['scope']) for x in dedup[:6]]}")
    return dedup


def obtener_ausencias_usuario_en_rango(db: Session, usuario_email: str, start: date, end: date):
    """
    Ausencias del usuario que tocan el rango [start, end] (cualquier estado).
    """
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
    """
    Devuelve eventos ya deduplicados. Para festivos, 1 chip por (fecha, scope):
    prioridad de especificidad solo afecta a empates exactos (arriba ya deduplicado).
    """
    user = obtener_usuario_por_id(db, user_id)
    if not user:
        return []

    eventos: List[Dict] = []

    # FESTIVOS (ya filtrados + deduplicados)
    festivos = obtener_festivos_por_usuario_en_rango(db, user_id, start, end)

    # Última red de seguridad: 1 por (fecha, scope)
    seen = set()
    for f in festivos:
        d = f.get("date") or f.get("fecha")
        n = f.get("name") or f.get("nombre")
        s = f.get("scope") or ""  # 'national' | 'region' | 'province' | 'local'
        if not d or not n:
            continue
        key = (d, s)
        if key in seen:
            continue
        seen.add(key)
        eventos.append({
            "fecha": d,
            "titulo": n,           # nombre real (tooltip)
            "type": "FESTIVO",
            "estado": None,
            "scope": s,            # pásalo a la UI: NACIONAL/REGIÓN/…
        })

    # AUSENCIAS (expandir por día)
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
