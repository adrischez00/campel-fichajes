from datetime import date as _date, timedelta
from typing import List
import os

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas, models
from app.auth import get_current_user  # <- TOKEN obligatorio
from app.models import User
from app import crud
router = APIRouter(prefix="/calendar", tags=["calendar"])


# -------------------------
# Utils
# -------------------------
def _ensure_postgres():
    url = os.getenv("DATABASE_URL", "")
    if url.startswith("sqlite"):
        raise HTTPException(
            status_code=501,
            detail="Este endpoint requiere PostgreSQL. Configura DATABASE_URL a Postgres.",
        )


def _last_day_of_month(year: int, month: int) -> _date:
    first = _date(year, month, 1)
    return (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


# -------------------------
# Cómputo laboral (se dejan igual)
# -------------------------
@router.get("/users/{user_id}/is-working")
def is_working(
    user_id: int,
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
):
    _ensure_postgres()
    q = text("SELECT is_working_for_user(:uid::int, :d::date) AS working")
    row = db.execute(q, {"uid": user_id, "d": date}).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return {"user_id": user_id, "date": date, "working": bool(row["working"])}


@router.get("/users/{user_id}/working-days")
def working_days(
    user_id: int,
    start: _date = Query(..., description="YYYY-MM-DD"),
    end: _date = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    

    """
    Cuenta días laborables entre start y end (inclusive):
    - Lunes a viernes
    - Excluye festivos aplicables al usuario (national/region/province/local)
    Devuelve también fines de semana y número total de días marcados como festivo.
    """
    if end < start:
        raise HTTPException(status_code=400, detail="El rango de fechas es inválido (end < start).")

    # Festivos aplicables al usuario (misma lógica que el feed)
    festivos = crud.obtener_festivos_por_usuario_en_rango(db, user_id, start, end)

    # Conjunto de fechas (YYYY-MM-DD) con festivo para ese usuario
    festivo_days = set()
    for f in festivos or []:
        d = f.get("date") or f.get("fecha")
        # normaliza a string YYYY-MM-DD
        if hasattr(d, "isoformat"):
            festivo_days.add(d.isoformat()[:10])
        else:
            festivo_days.add(str(d)[:10])

    holidays_total = len(festivo_days)

    # Recorre el rango y cuenta laborables
    working = 0
    weekends = 0
    cur = start
    while cur <= end:
        dow = cur.weekday()  # 0=Lunes ... 6=Domingo
        if dow >= 5:
            weekends += 1
        else:
            if cur.isoformat()[:10] not in festivo_days:
                working += 1
        cur += timedelta(days=1)

    return {
        "user_id": user_id,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "working_days": working,   # ← lo que necesita tu UI
        "weekends": weekends,
        "holidays": holidays_total # total de fechas festivas en el rango (caigan o no en finde)
    }

@router.get("/working-days")
def working_days_me(
    start: _date = Query(..., description="YYYY-MM-DD"),
    end: _date = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Igual que /users/{user_id}/working-days pero para el usuario autenticado.
    Descuenta sábados, domingos y festivos aplicables al usuario.
    """
    if end < start:
        raise HTTPException(status_code=400, detail="El rango de fechas es inválido (end < start).")

    # Festivos del usuario en el rango (misma lógica que el feed)
    festivos = crud.obtener_festivos_por_usuario_en_rango(db, current_user.id, start, end)

    # Normaliza a objetos date
    festivo_days: set[_date] = set()
    for f in festivos or []:
        d = f.get("date") or f.get("fecha")
        if isinstance(d, _date):
            festivo_days.add(d)
        else:
            try:
                festivo_days.add(_date.fromisoformat(str(d)[:10]))
            except Exception:
                pass

    laborables = 0
    fines = 0
    d = start
    while d <= end:
        if d.weekday() >= 5:
            fines += 1
        elif d not in festivo_days:
            laborables += 1
        d += timedelta(days=1)

    return {
        "user_id": current_user.id,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "working_days": laborables,                 # ← lo que lee el front
        "festivos": sorted(x.isoformat() for x in festivo_days if x.weekday() < 5),
        "fines_de_semana": fines,
    }




# -------------------------
# FESTIVOS autenticados
# -------------------------
@router.get("/{year}/{month}")
def month_marks_for_logged_user(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),  # <- obliga a ir con token
):
    """
    Devuelve SOLO los festivos aplicables al usuario autenticado:
    - nacionales
    - + su región/provincia/local (según user_locations / users.locality_code)
    - deduplicados
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=422, detail="El parámetro 'month' debe estar entre 1 y 12.")
    start = _date(year, month, 1)
    end = _last_day_of_month(year, month)
    items = crud.obtener_festivos_por_usuario_en_rango(db, current_user.id, start, end)
    return {"items": items}


# -------------------------
# Crear/actualizar marca de empresa (UPSERT)
# -------------------------
@router.post("/company")
def create_company_mark(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    mark: str = Query(..., pattern="^(holiday|workday)$"),
    name: str = Query(..., min_length=1),
    company_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),  # recomendable exigir login
):
    _ensure_postgres()
    q = text(
        """
        INSERT INTO calendar_marks (scope, mark, date, name, company_id, source)
        VALUES ('company', :mark::cal_mark, :date::date, :name, :cid, 'API')
        ON CONFLICT (
            scope, mark, date,
            COALESCE(region_code,'-'),
            COALESCE(province_code,'-'),
            COALESCE(locality_code,'-'),
            COALESCE(company_id,'00000000-0000-0000-0000-000000000000')
        )
        DO UPDATE SET name = EXCLUDED.name, imported_at = NOW(), source = 'API'
        RETURNING scope, mark, date, name, company_id;
        """
    )
    row = db.execute(q, {"mark": mark, "date": date, "name": name, "cid": company_id}).mappings().first()
    db.commit()
    return dict(row) if row else {}


# -------------------------
# Feed unificado (festivos + ausencias) del usuario logeado
# -------------------------
@router.get(
    "/events",
    response_model=List[schemas.CalendarEvent],
    summary="Eventos del usuario autenticado (festivos filtrados + ausencias)",
)
def my_calendar_events(
    start: _date = Query(..., description="YYYY-MM-DD"),
    end: _date = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if end < start:
        raise HTTPException(status_code=400, detail="El rango de fechas es inválido (end < start).")
    return crud.obtener_eventos_calendario(db, user_id=current_user.id, start=start, end=end)

@router.get("/working-days-python")
def working_days_me_python(
    start: _date = Query(...),
    end: _date = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # reutiliza el cálculo Python
    return working_days(user_id=current_user.id, start=start, end=end, db=db)




