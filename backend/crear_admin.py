from app.database import SessionLocal
from app.crud import crear_usuario

db = SessionLocal()
usuario = crear_usuario(db, "admin@campel.com", "admin123", "admin")
print(f"Usuario creado: {usuario.email} con rol {usuario.role}")