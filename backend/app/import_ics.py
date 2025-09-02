#!/usr/bin/env python3
import os, argparse
from datetime import datetime, date
from dateutil.tz import tzlocal
from icalendar import Calendar
import psycopg2
import psycopg2.extras as extras

def parse_args():
    p = argparse.ArgumentParser(description="Importa festivos ICS en calendar_marks (idempotente)")
    p.add_argument("--dsn", default=os.getenv("DATABASE_URL"),
                   help="Postgres DSN, ej: postgres://user:pass@host/db")
    p.add_argument("--ics", required=True, help="Ruta o fichero ICS")
    p.add_argument("--scope", required=True, choices=["national","region","province","local"])
    p.add_argument("--region-code")
    p.add_argument("--province-code")
    p.add_argument("--locality-code")
    p.add_argument("--source", default="ICS")
    return p.parse_args()

def ensure_date(v):
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    raise ValueError("Fecha ICS no reconocida")

def main():
    a = parse_args()
    if a.scope == "region" and not a.region_code:
        raise SystemExit("--scope region requiere --region-code")
    if a.scope == "province" and not a.province_code:
        raise SystemExit("--scope province requiere --province-code")
    if a.scope == "local" and not a.locality_code:
        raise SystemExit("--scope local requiere --locality-code")

    with open(a.ics, "rb") as f:
        cal = Calendar.from_ical(f.read())

    rows = []
    for comp in cal.walk("vevent"):
        summ = comp.get("summary")
        dt = comp.get("dtstart")
        if not summ or not dt:
            continue
        d = ensure_date(dt.dt)
        name = str(summ)
        rows.append({
            "scope": a.scope, "mark": "holiday", "date": d, "name": name,
            "region_code": a.region_code, "province_code": a.province_code,
            "locality_code": a.locality_code, "source": a.source
        })

    if not rows:
        print("Nada que importar (0 eventos).")
        return

    sql = """
    INSERT INTO calendar_marks
        (scope, mark, date, name, region_code, province_code, locality_code, source)
    VALUES
        (%(scope)s, %(mark)s, %(date)s, %(name)s, %(region_code)s, %(province_code)s, %(locality_code)s, %(source)s)
    ON CONFLICT (
        scope, mark, date,
        COALESCE(region_code,'-'),
        COALESCE(province_code,'-'),
        COALESCE(locality_code,'-'),
        COALESCE(company_id,'00000000-0000-0000-0000-000000000000')
    ) DO UPDATE SET
        name = EXCLUDED.name,
        source = EXCLUDED.source,
        created_at = NOW();
    """

    conn = psycopg2.connect(a.dsn)
    with conn, conn.cursor() as cur:
        extras.execute_batch(cur, sql, rows, page_size=200)
    print(f"Importadas/actualizadas {len(rows)} filas.")

if __name__ == "__main__":
    main()
