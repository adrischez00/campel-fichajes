import hashlib
from datetime import datetime
from app import models
from fpdf import FPDF
from fastapi.responses import FileResponse
import os
from collections import defaultdict

# ------------------------
# Hash para fichajes
# ------------------------
def generar_hash_fichaje(usuario: str, tipo: str, timestamp: str) -> str:
    data = f"{usuario}:{tipo}:{timestamp}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

# ------------------------
# Logs de acciones
# ------------------------
def log_evento(db, usuario: models.User, accion: str, detalle: str):
    log = models.LogAuditoria(
        accion=accion,
        detalle=detalle,
        usuario=usuario,
        timestamp=datetime.utcnow()
    )
    db.add(log)

# ------------------------
# Exportar PDF con logo
# ------------------------
def exportar_pdf(usuario_email: str, fichajes):
    class PDF(FPDF):
        def header(self):
            self.image("static/logo.png", 10, 8, 25)
            self.set_font("Arial", "B", 14)
            self.cell(0, 10, "Registro de fichajes - Campel", ln=True, align="C")
            self.ln(10)

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Empleado: {usuario_email}", ln=True)
    pdf.cell(0, 10, f"Exportado: {datetime.utcnow().isoformat()}", ln=True)
    pdf.ln(5)

    for f in fichajes:
        fecha = datetime.fromisoformat(f["timestamp"]).strftime("%Y-%m-%d %H:%M")
        pdf.cell(0, 10, f"{fecha} - {f.tipo} (Hash: {f.hash[:10]}...)", ln=True)

    filename = f"export_{usuario_email}.pdf"
    pdf.output(filename)
    return FileResponse(path=filename, filename=filename, media_type='application/pdf')

# ------------------------
# Resumen de fichajes por usuario
# ------------------------
def resumen_fichajes_por_usuario(fichajes, solicitudes):
    data = defaultdict(lambda: {'bloques': [], 'total_ms': 0})

    aprobadas = [s for s in solicitudes if s.estado == "aprobado"]

    eventos = [
        {
            "timestamp": f.timestamp.isoformat(),
            "tipo": f.tipo,
            "origen": "fichaje"
        } for f in fichajes
    ] + [
        {
            "timestamp": datetime.strptime(f"{s.fecha} {s.hora}", "%Y-%m-%d %H:%M").isoformat(),
            "tipo": s.tipo,
            "origen": "manual"
        } for s in aprobadas
    ]

    eventos.sort(key=lambda x: x["timestamp"])

    por_fecha = defaultdict(list)
    for e in eventos:
        fecha = datetime.fromisoformat(e["timestamp"]).astimezone().date().isoformat()
        por_fecha[fecha].append(e)

    resumen = {}
    for fecha, items in por_fecha.items():
        bloques = []
        pendiente = None

        for ev in items:
            ts = datetime.fromisoformat(ev["timestamp"])
            if ev["tipo"] == "entrada":
                if pendiente:
                    bloques.append({
                        "entrada": pendiente["timestamp"],
                        "salida": None,
                        "duracion": None,
                        "anomalia": "entrada sin salida"
                    })
                pendiente = ev
            elif ev["tipo"] == "salida":
                if pendiente:
                    t_entrada = datetime.fromisoformat(pendiente["timestamp"])
                    t_salida = ts
                    dur = int((t_salida - t_entrada).total_seconds())
                    bloques.append({
                        "entrada": pendiente["timestamp"],
                        "salida": ev["timestamp"],
                        "duracion": dur,
                        "anomalia": None
                    })
                    pendiente = None
                else:
                    bloques.append({
                        "entrada": None,
                        "salida": ev["timestamp"],
                        "duracion": None,
                        "anomalia": "salida sin entrada"
                    })

        if pendiente:
            bloques.append({
                "entrada": pendiente["timestamp"],
                "salida": None,
                "duracion": None,
                "anomalia": "entrada sin salida"
            })

        resumen[fecha] = {
            "bloques": bloques,
            "total": sum(b["duracion"] or 0 for b in bloques)
        }

    return resumen

# ------------------------
# Resumen con AUSENCIAS (extiende el anterior sin romperlo)
# ------------------------
from datetime import datetime, date, time, timedelta  # import local para no tocar cabecera

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

def _huecos_del_dia(intervalos_trabajo, dia_dt: date):
    ini = datetime.combine(dia_dt, time.min)
    fin = datetime.combine(dia_dt, time.max)
    ocupados = _merge_intervalos(intervalos_trabajo)
    huecos, cursor = [], ini
    for s, e in ocupados:
        if s > cursor:
            huecos.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < fin:
        huecos.append((cursor, fin))
    return huecos

def _interseccion_seg(a_ini, a_fin, b_ini, b_fin) -> int:
    ini = max(a_ini, b_ini)
    fin = min(a_fin, b_fin)
    if fin <= ini:
        return 0
    return int((fin - ini).total_seconds())

def _tramo_ausencia_en_dia(a, dia_dt: date):
    """Devuelve (ini_dt, fin_dt) de la ausencia 'a' acotada al día 'dia_dt'."""
    if a.parcial:
        # En día de inicio usamos hora_inicio; en día de fin, hora_fin. En intermedios: todo el día.
        if dia_dt == a.fecha_inicio and a.hora_inicio is not None:
            ini = datetime.combine(dia_dt, a.hora_inicio)
        else:
            ini = datetime.combine(dia_dt, time.min)
        if dia_dt == a.fecha_fin and a.hora_fin is not None:
            fin = datetime.combine(dia_dt, a.hora_fin)
        else:
            fin = datetime.combine(dia_dt, time.max)
    else:
        ini = datetime.combine(dia_dt, time.min)
        fin = datetime.combine(dia_dt, time.max)
    return ini, fin

def resumen_fichajes_por_usuario_con_ausencias(fichajes, solicitudes, ausencias):
    """
    Extiende 'resumen_fichajes_por_usuario' añadiendo:
      - 'ausencias_retribuidas' (segundos)
      - 'total_computado'       (segundos = total + ausencias_retribuidas)
      - 'ausencias_detalle'     (lista con tipo/subtipo/retribuida/segundos_sumados)

    Parámetros esperados:
      - fichajes: objetos con .timestamp (datetime) y .tipo ('entrada'|'salida')
      - solicitudes: objetos con .estado, .fecha (YYYY-MM-DD), .hora (HH:MM), .tipo
      - ausencias: objetos con campos de tu modelo (estado, fecha_inicio/fin, hora_inicio/fin, parcial, retribuida, tipo, subtipo)
    """
    # 1) Resumen base (tu función actual)
    base = resumen_fichajes_por_usuario(fichajes, solicitudes)

    # 2) Para cada día del resumen, calcular relleno por ausencias retribuidas
    for fecha_str, info in base.items():
        # 'fecha_str' viene como 'YYYY-MM-DD'
        dia_dt = datetime.strptime(fecha_str, "%Y-%m-%d").date()

        # Intervalos de trabajo reales de ese día (solo pares completos)
        intervalos_trabajo = []
        for b in info.get("bloques", []):
            if b.get("entrada") and b.get("salida") and b.get("duracion"):
                ini = datetime.fromisoformat(b["entrada"])
                fin = datetime.fromisoformat(b["salida"])
                intervalos_trabajo.append((ini, fin))
        intervalos_trabajo = _merge_intervalos(intervalos_trabajo)

        huecos = _huecos_del_dia(intervalos_trabajo, dia_dt)

        # Filtrar ausencias que impactan el día y estén aprobadas
        aus_dia = [
            a for a in ausencias
            if getattr(a, "estado", "PENDIENTE") == "APROBADA"
            and a.fecha_fin >= dia_dt and a.fecha_inicio <= dia_dt
        ]

        # 3) Sumar SOLO retribuidas y SOLO en huecos (evitar doble conteo)
        aus_retrib_seg = 0
        aus_detalle = []
        for a in aus_dia:
            a_ini, a_fin = _tramo_ausencia_en_dia(a, dia_dt)
            acum = 0
            if a.retribuida:
                for h_ini, h_fin in huecos:
                    acum += _interseccion_seg(a_ini, a_fin, h_ini, h_fin)
                aus_retrib_seg += acum
            # detalle (también para no retribuidas con 0s)
            aus_detalle.append({
                "tipo": a.tipo,
                "subtipo": a.subtipo,
                "parcial": bool(a.parcial),
                "retribuida": bool(a.retribuida),
                "segundos_sumados": int(acum if a.retribuida else 0),
            })

        # 4) Anexar sin romper claves existentes
        info["ausencias_retribuidas"] = int(aus_retrib_seg)               # segundos
        info["total_computado"] = int(info["total"]) + int(aus_retrib_seg) # segundos
        info["ausencias_detalle"] = aus_detalle

    return base

