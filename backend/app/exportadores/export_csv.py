import csv
from io import StringIO
from fastapi.responses import Response
from .base import ExportadorBase

class ExportadorCSV(ExportadorBase):
    def __init__(self, logs):
        self.logs = logs

    def exportar(self):
        if not self.logs:
            contenido = "# NO HAY DATOS PARA EXPORTAR\n"
            return Response(
                content=contenido,
                media_type=self.tipo_mime(),
                headers={"Content-Disposition": f"attachment; filename={self.nombre_archivo()}"}
            )

        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')

        for fila in self.logs:
            usuario = fila.get("usuario", "")
            fecha = fila.get("fecha", "")
            intervalos = fila.get("intervalos", [])
            total_dia = fila.get("total", "")

            writer.writerow([f"USUARIO: {usuario}"])
            writer.writerow([f"FECHA: {fecha}"])
            writer.writerow([])
            writer.writerow(["ENTRADA", "SALIDA", "DURACIÓN", "ENTRADA MANUAL", "SALIDA MANUAL", "MOTIVO ENTRADA", "MOTIVO SALIDA"])

            for i in intervalos:
                entrada = i.get("entrada", "")
                salida = i.get("salida", "")
                duracion = i.get("duracion", "")
                manual_entrada = "SI" if i.get("manualEntrada") else ""
                manual_salida = "SI" if i.get("manualSalida") else ""
                motivo_entrada = i.get("motivoEntrada", "").strip()
                motivo_salida = i.get("motivoSalida", "").strip()

                writer.writerow([entrada, salida, duracion, manual_entrada, manual_salida, motivo_entrada, motivo_salida])

            writer.writerow([])
            writer.writerow(["", "", "", "TOTAL JORNADA DEL DÍA:", total_dia])
            writer.writerow(["="*80])
            writer.writerow([])

        contenido = output.getvalue().encode("utf-8-sig")

        return Response(
            content=contenido,
            media_type=self.tipo_mime(),
            headers={"Content-Disposition": f"attachment; filename={self.nombre_archivo()}"}
        )

    def nombre_archivo(self) -> str:
        return "logs_auditoria.csv"

    def tipo_mime(self) -> str:
        return "text/csv"


