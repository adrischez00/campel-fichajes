import os, sys, time, traceback

print("[BOOT] starting image:", os.getenv("IMAGE_MARK"), flush=True)

# 1) Probar import de la app
try:
    print("[BOOT] importing app.main:app ...", flush=True)
    from app.main import app
    print("[BOOT] import OK", flush=True)
except Exception as e:
    print("[BOOT] import FAILED:", repr(e), file=sys.stderr, flush=True)
    traceback.print_exc()
    time.sleep(300)  # deja tiempo para leer logs
    sys.exit(1)

# 2) Levantar uvicorn desde Python (para ver tracebacks reales)
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    try:
        import uvicorn
        print(f"[BOOT] starting uvicorn on 0.0.0.0:{port}", flush=True)
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="debug",
            proxy_headers=True,
            forwarded_allow_ips="*",
        )
    except Exception as e:
        print("[BOOT] uvicorn FAILED:", repr(e), file=sys.stderr, flush=True)
        traceback.print_exc()
        time.sleep(300)
        sys.exit(1)
