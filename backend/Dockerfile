FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Carpetas usadas por StaticFiles (por si acaso)
RUN mkdir -p static ics

# --- DIAGNÓSTICO: primero probamos el import y mostramos traceback ---
# Si el import va bien, arrancamos uvicorn; si no, vemos el error claro en logs.
CMD sh -c 'python - << "PY"\n\
import traceback, sys\n\
print(">>> checking import app.main ...")\n\
try:\n\
    import app.main  # <-- aquí fallará si falta un paquete o hay un error de código\n\
    print(">>> import OK")\n\
except Exception:\n\
    print(">>> import FAILED! Full traceback:")\n\
    traceback.print_exc()\n\
    sys.exit(1)\n\
PY\n\
&& exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --log-level debug'
