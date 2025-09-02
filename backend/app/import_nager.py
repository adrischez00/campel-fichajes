# import_nager.py
import os
import argparse
from datetime import datetime
import requests
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("Falta DATABASE_URL en el entorno.")

engine = create_engine(DATABASE_URL)

NAGER_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/ES"

def upsert_mark(conn, *, scope, date_, name, region_code=None, province_code=None, locality_code=None, source="NAGER"):
    # UPSERT sin índice único usando "IS NOT DISTINCT FROM" (NULL-safe)
    sel = text("""
        SELECT id FROM calendar_marks
        WHERE scope = :scope AND mark = 'holiday' AND date = :date
          AND region_code  IS NOT DISTINCT FROM :r
          AND province_code IS NOT DISTINCT FROM :p
          AND locality_code IS NOT DISTINCT FROM :l
        LIMIT 1
    """)
    row = conn.execute(sel, {"scope": scope, "date": date_, "r": region_code, "p": province_code, "l": locality_code}).mappings().first()
    if row:
        upd = text("""
            UPDATE calendar_marks
               SET name=:name, source=:source, imported_at=NOW()
             WHERE id=:id
        """)
        conn.execute(upd, {"id": row["id"], "name": name, "source": source})
    else:
        ins = text("""
            INSERT INTO calendar_marks (scope, mark, date, name, region_code, province_code, locality_code, source, imported_at)
            VALUES (:scope, 'holiday', :date, :name, :r, :p, :l, :source, NOW())
        """)
        conn.execute(ins, {"scope": scope, "date": date_, "name": name, "r": region_code, "p": province_code, "l": locality_code, "source": source})

def import_year(year: int):
    print(f"→ Importando festivos ES {year} (nacional + CCAA) …")
    url = NAGER_URL.format(year=year)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    with engine.begin() as conn:
        total = 0
        for item in data:
            # Nager: localName (ES) y name (EN). Usamos localName si existe.
            name = item.get("localName") or item.get("name")
            date_ = item["date"]  # 'YYYY-MM-DD'
            counties = item.get("counties")  # None => nacional, lista => CCAA (ISO 3166-2)
            if not counties:
                # Nacional
                upsert_mark(conn, scope="national", date_=date_, name=name)
                total += 1
            else:
                # Regional (ej. 'ES-MD', 'ES-AN', …)
                for c in counties:
                    if not c.startswith("ES-"):
                        continue
                    upsert_mark(conn, scope="region", date_=date_, name=name, region_code=c)
                    total += 1
        print(f"   He insertado/actualizado {total} filas para {year}.")

def main():
    parser = argparse.ArgumentParser(description="Importa festivos ES (nacional + CCAA) desde Nager.Date")
    parser.add_argument("--years", nargs="+", type=int, help="Años a importar. Ej: --years 2024 2025")
    args = parser.parse_args()

    years = args.years or [datetime.now().year, datetime.now().year + 1]
    for y in years:
        import_year(y)

if __name__ == "__main__":
    main()
