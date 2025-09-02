from app.exportadores.export_csv import ExportadorCSV
from app.exportadores.export_pdf import ExportadorPDF
from app.exportadores.export_json import ExportadorJSON
from app.exportadores.export_xlsx import ExportadorXLSX
from app.exportadores.export_xml import ExportadorXML

def obtener_exportador(formato: str, logs: list):
    formato = formato.lower()

    if formato == "csv":
        return ExportadorCSV(logs)
    elif formato == "pdf":
        return ExportadorPDF(logs)
    elif formato == "json":
        return ExportadorJSON(logs)
    elif formato == "xlsx":
        return ExportadorXLSX(logs)
    elif formato == "xml":
        return ExportadorXML(logs)
    else:
        raise ValueError(f"Formato no soportado: {formato}")
