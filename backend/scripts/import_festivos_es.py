# backend/scripts/import_festivos_es.py

from __future__ import annotations
import os, sys, argparse
from datetime import date
from typing import Iterable, List, Dict, Tuple, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

# -----------------------------
# Config
# -----------------------------
LANG = "es"
MARK = "holiday"
NATIONAL_SCOPE = "national"
REGION_SCOPE = "region"

# Santiago Apóstol: por defecto, SOLO Galicia
ALLOW_SANTIAGO_REGIONS = {"ES-GA"}  # añade aquí si alguna CCAA lo tiene oficialmente

# Exclusiones adicionales por (region_code, date)
EXCLUDE: set[Tuple[str, date]] = set()


# -----------------------------
# Utilidades DB
# -----------------------------
def open_conn() -> Connection:
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL no definido (usa backend/.env).", file=sys.stderr)
        sys.exit(1)
    engine = create_engine(dsn)
    return engine.connect()

def _find_existing(conn: Connection, *, scope: str, mark: str, d: date,
                   region_code: Optional[str], province_code: Optional[str], locality_code: Optional[str]) -> Optional[Dict]:
    sel = text("""
        SELECT id, name
        FROM calendar_marks
        WHERE scope = :scope AND mark = :mark AND date = :date
          AND COALESCE(region_code,'') = COALESCE(:region_code,'')
          AND COALESCE(province_code,'') = COALESCE(:province_code,'')
          AND COALESCE(locality_code,'') = COALESCE(:locality_code,'')
        LIMIT 1
    """)
    row = conn.execute(sel, {
        "scope": scope, "mark": mark, "date": d,
        "region_code": region_code, "province_code": province_code, "locality_code": locality_code
    }).mappings().first()
    return dict(row) if row else None

def _update_name_if_needed(conn: Connection, rec_id: int, name: str, source: str):
    upd = text("UPDATE calendar_marks SET name=:name, source=:source WHERE id=:id")
    conn.execute(upd, {"id": rec_id, "name": name, "source": source})

def _insert(conn: Connection, *, scope: str, mark: str, d: date, name: str,
            region_code: Optional[str], province_code: Optional[str], locality_code: Optional[str], source: str):
    ins = text("""
        INSERT INTO calendar_marks (scope, mark, date, name, region_code, province_code, locality_code, source)
        VALUES (:scope, :mark, :date, :name, :region_code, :province_code, :locality_code, :source)
    """)
    conn.execute(ins, {
        "scope": scope, "mark": mark, "date": d, "name": name,
        "region_code": region_code, "province_code": province_code, "locality_code": locality_code,
        "source": source
    })

def upsert_mark(conn: Connection, *, scope: str, d: date, name: str,
                region_code: Optional[str] = None,
                province_code: Optional[str] = None,
                locality_code: Optional[str] = None,
                source: str = "holidays-py"):
    found = _find_existing(
        conn, scope=scope, mark=MARK, d=d,
        region_code=region_code, province_code=province_code, locality_code=locality_code
    )
    if found:
        if found["name"] != name:
            _update_name_if_needed(conn, found["id"], name, source)
        return
    _insert(conn, scope=scope, mark=MARK, d=d, name=name,
            region_code=region_code, province_code=province_code, locality_code=locality_code, source=source)


# -----------------------------
# Importadores
# -----------------------------
def _years_range(y_from: int, y_to: int) -> List[int]:
    if y_to < y_from:
        y_from, y_to = y_to, y_from
    return list(range(y_from, y_to + 1))

def _load_nat(years: Iterable[int]) -> Dict[int, Dict[date, str]]:
    import holidays as hd
    out: Dict[int, Dict[date, str]] = {}
    for y in years:
        out[y] = dict(hd.country_holidays("ES", years=y, language="es"))
    return out

def _list_regions(conn: Connection) -> List[Tuple[str, str]]:
    try:
        rows = conn.execute(text("SELECT code FROM regions WHERE country_code='ES'")).fetchall()
        codes = [r[0] for r in rows if r and r[0]]
    except Exception:
        codes = [
            "ES-AN","ES-AR","ES-AS","ES-CB","ES-CE","ES-CL","ES-CM","ES-CN",
            "ES-CT","ES-EX","ES-GA","ES-IB","ES-RI","ES-MD","ES-ML","ES-MC","ES-NC","ES-PV","ES-VC",
        ]
    return [(c, c.split("-", 1)[1]) for c in codes if "-" in c]

def _should_skip_region_day(region_code: str, d: date, name: str) -> bool:
    nlow = name.lower()
    # Regla Santiago Apóstol: permitir solo en CCAA listadas
    if "santiago" in nlow or "saint james" in nlow:
        return region_code not in ALLOW_SANTIAGO_REGIONS
    # Aquí puedes añadir más reglas específicas si detectas otras anomalías:
    # if "algo raro" in nlow and region_code in {...}: return True
    return False

def import_national_and_regions(conn: Connection, y_from: int, y_to: int, only_region: Optional[str] = None):
    import holidays as hd

    years = _years_range(y_from, y_to)
    nat_by_year = _load_nat(years)

    # 1) Nacionales
    for y in years:
        for d, name in nat_by_year[y].items():
            upsert_mark(conn, scope=NATIONAL_SCOPE, d=d, name=name, source="ES-national")

    # 2) Regionales (CCAA)
    regions = _list_regions(conn)
    for iso_code, subdiv in regions:
        if only_region and iso_code != only_region:
            continue

        for y in years:
            try:
                reg = hd.country_holidays("ES", years=y, subdiv=subdiv, language="es")
            except Exception:
                continue

            nat_days = set(nat_by_year[y].keys())
            for d, name in reg.items():
                if d in nat_days:
                    continue
                if (iso_code, d) in EXCLUDE:
                    continue
                if _should_skip_region_day(iso_code, d, name):
                    continue
                upsert_mark(conn,
                            scope=REGION_SCOPE,
                            d=d,
                            name=name,
                            region_code=iso_code,
                            source=f"ES-region:{subdiv}")


# -----------------------------
# CLI
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="Importa festivos (nacionales + CCAA) a calendar_marks.")
    ap.add_argument("--from", dest="y_from", type=int, required=True)
    ap.add_argument("--to", dest="y_to", type=int, required=True)
    ap.add_argument("--only-region", dest="only_region")
    args = ap.parse_args()

    with open_conn() as conn:
        tx = conn.begin()
        try:
            import_national_and_regions(conn, args.y_from, args.y_to, only_region=args.only_region)
            tx.commit()
            print("OK: importación completada.")
        except Exception as e:
            tx.rollback()
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
