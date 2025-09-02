# backend/app/exportadores/export_xml.py
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from fastapi.responses import Response
from datetime import datetime
from .base import ExportadorBase

class ExportadorXML(ExportadorBase):
    """
    Exportador profesional de logs en formato XML.
    Cumple normativa laboral 2025-2026.
    Estructura clara y adaptable a sistemas antiguos (ERP, etc.).
    """

    def exportar(self, datos):
        raiz = Element("logs")

        for entrada in datos:
            log = SubElement(raiz, "log")

            usuario = SubElement(log, "usuario_email")
            usuario.text = entrada.get("usuario_email", "")

            tipo = entrada.get("tipo", "")
            nodo_tipo = SubElement(log, "tipo")
            nodo_tipo.text = tipo

            timestamp = entrada.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            fecha = SubElement(log, "fecha")
            fecha.text = timestamp.strftime("%d/%m/%Y") if timestamp else ""

            hora = SubElement(log, "hora")
            hora_text = timestamp.strftime("%H:%M:%S") if timestamp else ""
            if entrada.get("is_manual"):
                hora.text = hora_text + " 📝"
            else:
                hora.text = hora_text

            if entrada.get("is_manual") and entrada.get("motivo"):
                motivo = SubElement(log, "motivo")
                limpio = entrada["motivo"].replace("\n", " ").replace("\r", " ").strip()
                tipo_fmt = tipo.capitalize()
                motivo.text = f'{tipo_fmt} manual: "{limpio}"'

        # Prettify XML
        xml_bytes = minidom.parseString(tostring(raiz)).toprettyxml(indent="  ", encoding="utf-8")

        return Response(
            content=xml_bytes,
            media_type=self.tipo_mime(),
            headers={
                "Content-Disposition": f"attachment; filename={self.nombre_archivo()}"
            }
        )

    def nombre_archivo(self) -> str:
        return "logs_auditoria.xml"

    def tipo_mime(self) -> str:
        return "application/xml"

