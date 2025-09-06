# backend/app/main.py
import os
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status, Header, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.routes import auth as auth_routes
from app import database, crud, auth, utils, models
from app.database import engine, get_db
from app.models import Base, User
from app.schemas import UserOut, UsuarioUpdate, UsuarioPassword
from app.routes import logs as logs_router
from app.routes import calendar
from app.schemas_solicitudes import ResolverSolicitudIn
from app.routes import ausencias as ausencias_router
from app.auth import get_current_user

# ---------------- Bootstrapping DB ----------------
# Nota: mantenemos create_all porque ya lo usas. (Si tienes migraciones aparte, podemos desactivarlo.)
Base.metadata.create_all(bind=engine)

# ---------------- App ----------------
app = FastAPI(redirect_slashes=False)

# ---------------- Health ----------------
@app.get("/health")
def health():
    return {"ok": True}

# Alias canónico /api/health
app.add_api_route("/api/health", health, methods=["GET"])

# ---------------- CORS (Cloudflare Pages + previews + localhost) ----------------
STATIC_ALLOWED = [
    "https://sistema-fichajes.pages.dev",
    "https://campel-fichajes.pages.dev",
]

# Override por env para previews (útil si cambias de proveedor/host)
DEFAULT_PREVIEWS_REGEX = r"^https://[a-z0-9-]+\.(sistema-fichajes|campel-fichajes)\.pages\.dev$"
PAGES_PREVIEWS_REGEX = os.getenv("ALLOW_ORIGIN_REGEX", DEFAULT_PREVIEWS_REGEX)

# Local dev (Vite dev/preview/otros). Se puede anular con ALLOW_LOCALHOST=0
ALLOW_LOCALHOST = os.getenv("ALLOW_LOCALHOST", "1") not in ("0", "false", "False")
LOCALHOST_ALLOWED = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",     # vite preview
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Orígenes extra por env (coma-separado)
extra = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
ALLOWED_ORIGINS = list(dict.fromkeys(STATIC_ALLOWED + (LOCALHOST_ALLOWED if ALLOW_LOCALHOST else []) + extra))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=PAGES_PREVIEWS_REGEX,
    allow_credentials=True,   # si usas cookies httpOnly para refresh
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,              # reduce preflights repetidos
)

# ---------------- Modelos de entrada ----------------
class SolicitudManualIn(BaseModel):
    fecha: str
    hora: str
    tipo: str
    motivo: str

class RegistroIn(BaseModel):
    email: str
    password: str
    role: str = "employee"

# ==================== HANDLERS (lógica real) ====================

# ---- Auth (form-urlencoded estándar OAuth2PasswordRequestForm) ----
def login_handler(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.autenticar_usuario(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    token = auth.crear_token_acceso({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}

# ---- Usuarios / administración ----
def registrar_handler(
    datos: RegistroIn,
    db: Session = Depends(get_db),
    solicitante: User = Depends(get_current_user)
):
    if solicitante.role != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")
    existente = crud.obtener_usuario_por_email(db, datos.email)
    if existente:
        raise HTTPException(status_code=409, detail="Ya existe ese usuario")
    nuevo = crud.crear_usuario(db, datos.email, datos.password, datos.role)
    utils.log_evento(db, solicitante, "crear_usuario", f"Creó a {datos.email} como {datos.role}")
    return nuevo

def listar_usuarios_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")
    return db.query(User).all()

def actualizar_usuario_handler(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user)
):
    if usuario.role != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")
    return crud.editar_usuario(db, usuario_id, datos.email, datos.role)

def eliminar_usuario_handler(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user)
):
    if usuario.role != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")
    return crud.eliminar_usuario(db, usuario_id)

def restablecer_password_handler(
    usuario_id: int,
    datos: UsuarioPassword,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user)
):
    if usuario.role != "admin":
        raise HTTPException(status_code=403, detail="No autorizado")
    return crud.restablecer_password(db, usuario_id, datos.nueva_password)

# ---- Fichajes ----
def fichar_handler(
    tipo: str = Form(...),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user)
):
    return crud.crear_fichaje(db, tipo, usuario)

def obtener_fichajes_handler(usuario: str = Header(...), db: Session = Depends(get_db)):
    user = crud.obtener_usuario_por_email(db, usuario)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return crud.obtener_fichajes_usuario(db, user)

def resumen_fichajes_handler(
    db: Session = Depends(get_db),
    usuario: User = Depends(get_current_user)
):
    return crud.resumen_fichajes_usuario(db, usuario)

def resumen_semana_handler(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return crud.resumen_semana_usuario(db, current_user)

# ---- Solicitudes ----
def solicitar_fichaje_manual_handler(data: SolicitudManualIn, usuario: str = Header(...), db: Session = Depends(get_db)):
    user = crud.obtener_usuario_por_email(db, usuario)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return crud.crear_solicitud_manual(db, data, user)

def listar_solicitudes_handler(db: Session = Depends(get_db)):
    return crud.listar_solicitudes(db)

def resolver_solicitud_handler(
    req: Request,
    body: ResolverSolicitudIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="No autorizado")

    ip = req.client.host if req and req.client else None
    try:
        if body.aprobar:
            s = crud.aprobar_solicitud(db, body.id, admin=current_user, ip=ip)
        else:
            s = crud.rechazar_solicitud(db, body.id, admin=current_user,
                                        motivo_rechazo=body.motivo_rechazo, ip=ip)
        return {"ok": True, "solicitud": s.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---- Export ----
def exportar_handler(usuario: str, db: Session = Depends(get_db)):
    usuario = usuario.strip()
    user = crud.obtener_usuario_por_email(db, usuario)
    if not user:
        raise HTTPException(status_code=404, detail=f"Usuario '{usuario}' no encontrado")
    fichajes = crud.obtener_fichajes_usuario(db, user)
    return utils.exportar_pdf(user.email, fichajes)

# ==================== MONTAJE CANÓNICO (/api) ====================
# Routers funcionales (todos bajo /api)
app.include_router(auth_routes.router,     prefix="/api/auth", tags=["auth"])
app.include_router(calendar.router,         prefix="/api", tags=["calendar"])
app.include_router(ausencias_router.router, prefix="/api")          # router ya tiene prefix="/ausencias"
app.include_router(logs_router.router,      prefix="/api/logs")     # logs bajo /api/logs

# ---------------- LOGIN JSON (compatibilidad frontend) ----------------
class LoginJSON(BaseModel):
    email: str
    password: str

@app.post("/api/auth/login-json")
def login_json(body: LoginJSON, db: Session = Depends(get_db)):
    user = crud.autenticar_usuario(db, body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )
    token = auth.crear_token_acceso({"sub": user.email, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}

# Endpoints que estaban en main -> ahora canónicos bajo /api
app.add_api_route("/api/registrar",             registrar_handler,             methods=["POST"])
app.add_api_route("/api/usuarios",              listar_usuarios_handler,       methods=["GET"], response_model=List[UserOut])
app.add_api_route("/api/usuarios/{usuario_id}", actualizar_usuario_handler,    methods=["PUT"])
app.add_api_route("/api/usuarios/{usuario_id}", eliminar_usuario_handler,      methods=["DELETE"])
app.add_api_route("/api/usuarios/{usuario_id}/restablecer", restablecer_password_handler, methods=["POST"])
app.add_api_route("/api/fichar",                fichar_handler,                methods=["POST"])
app.add_api_route("/api/fichajes",              obtener_fichajes_handler,      methods=["GET"])
app.add_api_route("/api/resumen-fichajes",      resumen_fichajes_handler,      methods=["GET"])
app.add_api_route("/api/resumen-semana",        resumen_semana_handler,        methods=["GET"])
app.add_api_route("/api/solicitar-fichaje-manual", solicitar_fichaje_manual_handler, methods=["POST"])
app.add_api_route("/api/solicitudes",           listar_solicitudes_handler,    methods=["GET"])
app.add_api_route("/api/resolver-solicitud",    resolver_solicitud_handler,    methods=["POST"])
app.add_api_route("/api/exportar-pdf",          exportar_handler,              methods=["GET"])

# ==================== REDIRECTS LEGACY (sin /api -> /api) ====================
# Nota: 307 conserva método y body en POST/PUT/DELETE.

# Auth
@app.api_route("/login", methods=["POST"], include_in_schema=False)
def legacy_login_redirect():
    return RedirectResponse(url="/api/auth/login", status_code=307)

@app.api_route("/auth/login", methods=["POST"], include_in_schema=False)
def legacy_auth_login_redirect():
    return RedirectResponse(url="/api/auth/login", status_code=307)

# Usuarios
@app.api_route("/registrar", methods=["POST"], include_in_schema=False)
def legacy_registrar_redirect():
    return RedirectResponse(url="/api/registrar", status_code=307)

@app.api_route("/usuarios", methods=["GET"], include_in_schema=False)
def legacy_listar_usuarios_redirect():
    return RedirectResponse(url="/api/usuarios", status_code=307)

@app.api_route("/usuarios/{usuario_id}", methods=["PUT"], include_in_schema=False)
def legacy_actualizar_usuario_redirect(usuario_id: int):
    return RedirectResponse(url=f"/api/usuarios/{usuario_id}", status_code=307)

@app.api_route("/usuarios/{usuario_id}", methods=["DELETE"], include_in_schema=False)
def legacy_eliminar_usuario_redirect(usuario_id: int):
    return RedirectResponse(url=f"/api/usuarios/{usuario_id}", status_code=307)

@app.api_route("/usuarios/{usuario_id}/restablecer", methods=["POST"], include_in_schema=False)
def legacy_restablecer_password_redirect(usuario_id: int):
    return RedirectResponse(url=f"/api/usuarios/{usuario_id}/restablecer", status_code=307)

# Fichajes
@app.api_route("/fichar", methods=["POST"], include_in_schema=False)
def legacy_fichar_redirect():
    return RedirectResponse(url="/api/fichar", status_code=307)

@app.api_route("/fichajes", methods=["GET"], include_in_schema=False)
def legacy_fichajes_redirect():
    return RedirectResponse(url="/api/fichajes", status_code=307)

@app.api_route("/resumen-fichajes", methods=["GET"], include_in_schema=False)
def legacy_resumen_fichajes_redirect():
    return RedirectResponse(url="/api/resumen-fichajes", status_code=307)

@app.api_route("/resumen-semana", methods=["GET"], include_in_schema=False)
def legacy_resumen_semana_redirect():
    return RedirectResponse(url="/api/resumen-semana", status_code=307)

# Solicitudes
@app.api_route("/solicitar-fichaje-manual", methods=["POST"], include_in_schema=False)
def legacy_solicitar_manual_redirect():
    return RedirectResponse(url="/api/solicitar-fichaje-manual", status_code=307)

@app.api_route("/solicitudes", methods=["GET"], include_in_schema=False)
def legacy_listar_solicitudes_redirect():
    return RedirectResponse(url="/api/solicitudes", status_code=307)

@app.api_route("/resolver-solicitud", methods=["POST"], include_in_schema=False)
def legacy_resolver_solicitud_redirect():
    return RedirectResponse(url="/api/resolver-solicitud", status_code=307)

# Export
@app.api_route("/exportar-pdf", methods=["GET"], include_in_schema=False)
def legacy_exportar_redirect():
    return RedirectResponse(url="/api/exportar-pdf", status_code=307)

# Routers legacy (wildcards) -> /api
@app.api_route("/logs/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], include_in_schema=False)
def legacy_logs_wildcard_redirect(path: str):
    return RedirectResponse(url=f"/api/logs/{path}", status_code=307)

@app.api_route("/ausencias/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], include_in_schema=False)
def legacy_ausencias_wildcard_redirect(path: str):
    return RedirectResponse(url=f"/api/ausencias/{path}", status_code=307)

# ---------------- Static ----------------
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------- Entrypoint (local dev) ----------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
