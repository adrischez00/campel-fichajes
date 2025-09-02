# 🕒 Campel Fichajes

Sistema legal de registro horario para empleados, conforme al RD 8/2019 y al anteproyecto de ley laboral 2025.

---

## 🛠️ Tecnologías

- Backend: **FastAPI + PostgreSQL + SQLAlchemy**
- Frontend: **React + Vite + Tailwind CSS**
- Seguridad: JWT, bcrypt, hash SHA-256, logs de auditoría
- Exportación: PDF con logo corporativo

---

## 📦 Requisitos

### Backend
- Python 3.11+
- PostgreSQL (local o cloud)

### Frontend
- Node.js 18+

---

## 🚀 Ejecución local

### 1. Backend

```bash
cd backend
python -m venv env
source env/bin/activate  # o env\Scripts\activate en Windows
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` con tu cadena `DATABASE_URL` y `SECRET_KEY`.

Luego:

```bash
uvicorn app.main:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Accede a `http://localhost:5173`
---

## 🌐 Despliegue en producción

### Railway (backend + PostgreSQL)
1. Crear nuevo proyecto
2. Importar desde GitHub (carpeta `backend`)
3. Añadir base de datos PostgreSQL
4. Configurar variables de entorno

### Vercel (frontend)
1. Crear proyecto desde `frontend`
2. Añadir variable `VITE_API_URL=https://tu-api.railway.app`
3. Deploy

---

## ✅ Cumple la normativa

- Registro horario diario
- Firma digital (hash)
- Exportable en PDF
- Logs de auditoría y control de cambios
- Sin Excel ni papel
