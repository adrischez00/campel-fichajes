import json
from fastapi.responses import Response
from datetime import datetime
from collections import defaultdict
from .base import ExportadorBase

class ExportadorJSON(ExportadorBase):
    """
    Exportador profesional de logs en JSON agrupado por usuario y fecha.
    Incluye intervalos, duración, símbolos de fichajes manuales (📝) y motivos.
    """
    def __init__(self, datos):
        self.datos = datos

    def exportar(self):
        agrupados = defaultdict(lambda: defaultdict(list))

        # Agrupar por usuario y día
        for log in self.datos:
            log = dict(log)
            usuario = log.get("usuario_email")
            tipo = log.get("tipo")
            timestamp = log.get("timestamp")
            is_manual = log.get("is_manual", False)
            motivo = log.get("motivo", "")

            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            fecha = timestamp.strftime("%d/%m/%Y")
            agrupados[usuario][fecha].append({
                "tipo": tipo,
                "timestamp": timestamp,
                "is_manual": is_manual,
                "motivo": motivo.strip()
            })

        salida_final = []

        for usuario, fechas in agrupados.items():
            for fecha, fichajes in fechas.items():
                fichajes.sort(key=lambda x: x["timestamp"])
                intervalos = []
                total_ms = 0
                entrada = None
                entrada_manual = False
                motivo_entrada = ""

                for f in fichajes:
                    tipo = f["tipo"]
                    ts = f["timestamp"]
                    is_manual = f["is_manual"]
                    motivo = f["motivo"]

                    if tipo == "entrada":
                        entrada = ts
                        entrada_manual = is_manual
                        motivo_entrada = motivo
                    elif tipo == "salida" and entrada:
                        dur_ms = int((ts - entrada).total_seconds() * 1000)
                        total_ms += dur_ms
                        intervalo = {
                            "entrada": entrada.strftime("%H:%M:%S") + (" 📝" if entrada_manual else ""),
                            "salida": ts.strftime("%H:%M:%S") + (" 📝" if is_manual else ""),
                            "duracion": self._formato_duracion(dur_ms)
                        }
                        if entrada_manual and motivo_entrada:
                            intervalo["motivo_entrada"] = motivo_entrada
                        if is_manual and motivo:
                            intervalo["motivo_salida"] = motivo

                        intervalos.append(intervalo)
                        entrada = None
                        motivo_entrada = ""

                resumen = {
                    "usuario": usuario,
                    "fecha": fecha,
                    "intervalos": intervalos,
                    "total": self._formato_duracion(total_ms)
                }

                salida_final.append(resumen)

        # Generar JSON con indentado y UTF-8
        contenido = json.dumps(salida_final, indent=2, ensure_ascii=False)

        return Response(
            content=contenido,
            media_type=self.tipo_mime(),
            headers={"Content-Disposition": f"attachment; filename={self.nombre_archivo()}"}
        )

    def nombre_archivo(self) -> str:
        return "logs_auditoria.json"

    def tipo_mime(self) -> str:
        return "application/json"

    def _formato_duracion(self, ms: int) -> str:
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        return f"{h}h {m}min" if h else f"{m}min"
