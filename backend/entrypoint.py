import os, sys, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("boot")

def require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        log.error("Missing required env var: %s", name)
        sys.exit(1)
    return val

def main():
    # Requisitos mínimos para arrancar
    secret = require("SECRET_KEY")
    db_url = require("DATABASE_URL")
    port = int(os.getenv("PORT", "8080"))

    log.info("Starting app on port %s", port)
    # No mostramos valores, solo nombres para no filtrar secretos
    log.info("Env OK: SECRET_KEY, DATABASE_URL")

    # Arranque uvicorn (con exec para ser PID 1)
    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--proxy-headers",
            "--forwarded-allow-ips", "*",
        ],
    )

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Fatal error on startup")
        sys.exit(1)

