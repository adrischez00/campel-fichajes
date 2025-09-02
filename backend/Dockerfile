FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código (incluye app/, static/, ics/, etc.)
COPY . .

# Asegura carpetas usadas por StaticFiles si no se copian
RUN mkdir -p static ics

# Importante: usa $PORT y reemplaza el PID 1 con exec
CMD sh -c 'exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --proxy-headers --forwarded-allow-ips="*"'
