FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código (incluye app/, static/, ics/, etc.)
COPY . .

# Asegura carpetas usadas por StaticFiles si no se copian
RUN mkdir -p static ics

# IMPORTANTE: usar $PORT. En forma JSON NO se expande; usamos sh -c.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'"]
