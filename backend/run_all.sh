#!/usr/bin/env bash
set -euo pipefail

# DSN de Postgres; o usa variable de entorno DATABASE_URL
DSN="postgres://USER:PASS@HOST:PORT/DB"

# -------- Nacional --------
python3 import_ics.py --dsn "$DSN" --ics ./ics/ES_national.ics \
  --scope national

# -------- Comunidades Autónomas (ISO-3166-2) --------
# Rellena cada URL al ICS oficial de festivos autonómicos
declare -A ICS_REGION=(
  [ES-AN]=./ics/ES-AN.ics
  [ES-AR]=./ics/ES-AR.ics
  [ES-AS]=./ics/ES-AS.ics
  [ES-CB]=./ics/ES-CB.ics
  [ES-CE]=./ics/ES-CE.ics
  [ES-CL]=./ics/ES-CL.ics
  [ES-CM]=./ics/ES-CM.ics
  [ES-CN]=./ics/ES-CN.ics
  [ES-CT]=./ics/ES-CT.ics
  [ES-EX]=./ics/ES-EX.ics
  [ES-GA]=./ics/ES-GA.ics
  [ES-IB]=./ics/ES-IB.ics
  [ES-MC]=./ics/ES-MC.ics
  [ES-MD]=./ics/ES-MD.ics
  [ES-ML]=./ics/ES-ML.ics
  [ES-NC]=./ics/ES-NC.ics        # Navarra
  [ES-PV]=./ics/ES-PV.ics        # País Vasco
  [ES-RI]=./ics/ES-RI.ics        # La Rioja
  [ES-VC]=./ics/ES-VC.ics        # C. Valenciana
)

for code in "${!ICS_REGION[@]}"; do
  python3 import_ics.py --dsn "$DSN" --ics "${ICS_REGION[$code]}" \
    --scope region --region-code "$code"
done

# -------- Provincias (opcional) --------
# Si tienes ICS por provincia, usa el patrón ISO de tu tabla 'localities.province_code', ej. ES-MD-28
# Ejemplo: provincia de Madrid (28)
python3 import_ics.py --dsn "$DSN" --ics ./ics/ES-MD-28.ics \
  --scope province --province-code ES-MD-28

# -------- Locales (municipios) --------
# Usa el INE en tu 'locality_code', p.ej. Madrid capital: ES-MD-Madrid-28079
python3 import_ics.py --dsn "$DSN" --ics ./ics/ES-MD-Madrid-28079.ics \
  --scope local --locality-code ES-MD-Madrid-28079
