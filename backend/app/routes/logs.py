# backend/app/routes/logs.py
from fastapi import APIRouter, Depends, Query, HTTPException, Request, Response
from typing import Literal, Any
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud
from app.exportadores.export_csv import ExportadorCSV
from app.exportadores.export_json import ExportadorJSON
from app.exportadores.export_xlsx import ExportadorXLSX
from app.exportadores.export_pdf import ExportadorPDF
import traceback

router = APIRouter()

@router.get("")   # ← /logs   (sin barra final)
def obtener_logs(db: Session = Depends(get_db)):
    return crud.obtener_logs(db)

@router.post("/exportar_logs", response_class=Response)
async def exportar_logs(
    request: Request,
    formato: Literal["csv", "json", "pdf", "xlsx"] = Query("csv"),
    db: Session = Depends(get_db),
):
    try:
        datos: list[dict[str, Any]] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="❌ Error al leer el cuerpo de la solicitud")

    exportadores = {
        "csv": ExportadorCSV,
        "json": ExportadorJSON,
        "pdf": ExportadorPDF,
        "xlsx": ExportadorXLSX,
    }
    if formato not in exportadores:
        raise HTTPException(status_code=400, detail=f"❌ Formato '{formato}' no soportado")

    try:
        exportador = exportadores[formato](datos)
        return exportador.exportar()
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="❌ Error interno al exportar los logs")
