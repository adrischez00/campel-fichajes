# backend/entrypoint.py
import os, sys, importlib.util, traceback

def require_env(name, default=None, required=False, hide=False):
    val = os.getenv(name, default)
    if required and not val:
        print(f"[BOOT] FALTA variable {name}", file=sys.stderr)
        sys.exit(1)
    shown = "***" if hide else val
    print(f"[BOOT] {name} = {shown}")
    return val

def check_import(mod):
    if importlib.util.find_spec(mod) is None:
        print(f"[BOOT] FALTA paquete: {mod}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"[BOOT] import OK -> {mod}")

def main():
    print("=== BOOT START ===", flush=True)

    # Variables
    require_env("PORT", "8080")
    require_env("SECRET_KEY", required=True, hide=True)
    require_env("DATABASE_URL", required=True)

    # Paquetes críticos
    for m in ["fastapi", "uvicorn", "sqlalchemy", "psycopg", "PyJWT", "jose", "pydantic"]:
        check_import(m)

    # App import
    try:
        from app.main import app  # <- si tu app está aquí
        print("[BOOT] app.main:app import OK")
    except Exception:
        print("[BOOT] ERROR importando app.main:app")
        traceback.print_exc()
        sys.exit(1)

    # Lanzar uvicorn
    port = int(os.getenv("PORT", "8080"))
    print(f"[BOOT] Lanzando uvicorn en 0.0.0.0:{port}")
    try:
        import uvicorn
        uvicorn.run("app.main:app",
                    host="0.0.0.0",
                    port=port,
                    proxy_headers=True,
                    forwarded_allow_ips="*",
                    log_level="info")
    except Exception:
        print("[BOOT] uvicorn falló")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
