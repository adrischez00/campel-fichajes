from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Date, Time, Text,
    func, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# =========================
# Usuarios / Fichajes / Logs / Solicitudes / Ausencias
# =========================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="employee")

    fichajes = relationship("Fichaje", back_populates="usuario")
    solicitudes = relationship("SolicitudManual", back_populates="usuario")
    logs = relationship("LogAuditoria", back_populates="usuario")
    ausencias = relationship(
        "Ausencia",
        back_populates="usuario",
        primaryjoin="User.email==Ausencia.usuario_email",
        foreign_keys="[Ausencia.usuario_email]",
        passive_deletes=True,
    )


class Fichaje(Base):
    __tablename__ = "fichajes"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)  # 'entrada' | 'salida'
    # Aware + default en BD (UTC)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    hash = Column(String, nullable=False)
    is_manual = Column(Boolean, default=False)
    motivo = Column(String, nullable=True)

    # === NUEVO: estado de cómputo del fichaje (para “asistido”)
    # 'valido'       -> suma al total (normal)
    # 'provisional'  -> visible, NO suma hasta aprobación admin
    # 'invalidado'   -> visible, NO suma (rechazado por admin)
    validez = Column(String, nullable=False, default="valido", index=True)

    # === NUEVO: vínculo opcional a la solicitud que lo originó (1:1)
    solicitud_id = Column(Integer, ForeignKey("solicitudes.id", ondelete="SET NULL"), nullable=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    usuario = relationship("User", back_populates="fichajes")

    # Relación inversa a SolicitudManual (1:1 práctico)
    solicitud = relationship("SolicitudManual", back_populates="fichaje", uselist=False)


class SolicitudManual(Base):
    __tablename__ = "solicitudes"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String, nullable=False)          # input del usuario
    hora = Column(String, nullable=False)           # input del usuario
    tipo = Column(String, nullable=False)           # 'entrada' | 'salida'
    motivo = Column(String, nullable=False)
    estado = Column(String, default="pendiente")    # 'pendiente' | 'aprobada' | 'rechazada'
    # Aware + default en BD (UTC) (momento real solicitado)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user_id = Column(Integer, ForeignKey("users.id"))
    usuario = relationship("User", back_populates="solicitudes")

    # === NUEVO: metadatos de gestión (evita getattr en CRUD)
    gestionado_por_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    gestionado_por = relationship("User", foreign_keys=[gestionado_por_id])
    gestionado_en = Column(DateTime(timezone=True), nullable=True)
    motivo_rechazo = Column(String, nullable=True)
    ip_origen = Column(String, nullable=True)

    # === NUEVO: enlace 1:1 al fichaje resultante (si se generó)
    fichaje = relationship("Fichaje", back_populates="solicitud", uselist=False)


class LogAuditoria(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    accion = Column(String, nullable=False)
    detalle = Column(String, nullable=False)
    motivo = Column(String, nullable=True)
    # Aware + default en BD (UTC)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    usuario = relationship("User", back_populates="logs")


class Ausencia(Base):
    __tablename__ = "ausencias"

    id = Column(Integer, primary_key=True, index=True)
    usuario_email = Column(
        String, ForeignKey("users.email", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # 'VACACIONES'|'BAJA'|'ASUNTOS_PROPIOS'|'CITA_MEDICA'|'OTRA'
    tipo = Column(String, nullable=False)
    subtipo = Column(String, nullable=True)

    fecha_inicio = Column(Date, nullable=False, index=True)
    hora_inicio = Column(Time, nullable=True)
    fecha_fin = Column(Date, nullable=False, index=True)
    hora_fin = Column(Time, nullable=True)

    parcial = Column(Boolean, nullable=False, default=False)
    retribuida = Column(Boolean, nullable=False, default=True)

    # 'PENDIENTE'|'APROBADA'|'RECHAZADA'
    estado = Column(String, nullable=False, default="PENDIENTE", index=True)
    motivo = Column(Text, nullable=True)

    creada_por = Column(String, nullable=False)
    aprobada_por = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    usuario = relationship(
        "User",
        back_populates="ausencias",
        primaryjoin="User.email==Ausencia.usuario_email",
        foreign_keys=[usuario_email],
    )


# =========================
# Calendario & Localización (para Festivos)
# =========================

class Region(Base):
    """
    Comunidad Autónoma u otra división regional.
    """
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)      # p.ej. "Comunidad de Madrid"
    code = Column(String, index=True)          # código INE/ISO si aplica


class Locality(Base):
    """
    Municipio/localidad (si los usas para festivos locales).
    """
    __tablename__ = "localities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)      # p.ej. "Madrid"
    ine_code = Column(String, index=True)
    region_id = Column(Integer, ForeignKey("regions.id", ondelete="SET NULL"), index=True)


class UserLocation(Base):
    """
    Última localización conocida del usuario (para resolver sus festivos).
    """
    __tablename__ = "user_locations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    country_code = Column(String(2), nullable=False, default="ES", index=True)
    region_id = Column(Integer, ForeignKey("regions.id", ondelete="SET NULL"), index=True, nullable=True)
    locality_id = Column(Integer, ForeignKey("localities.id", ondelete="SET NULL"), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User")


class CalendarMark(Base):
    """
    Marca de calendario: festivos nacionales, autonómicos o locales.
    """
    __tablename__ = "calendar_marks"

    id = Column(Integer, primary_key=True)
    fecha = Column(Date, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=False, index=True)      # 'FESTIVO'
    ambito = Column(String, nullable=False, index=True)    # 'NACIONAL'|'AUTONOMICO'|'LOCAL'
    country_code = Column(String(2), nullable=False, default="ES", index=True)
    region_id = Column(Integer, ForeignKey("regions.id", ondelete="SET NULL"), index=True, nullable=True)
    locality_id = Column(Integer, ForeignKey("localities.id", ondelete="SET NULL"), index=True, nullable=True)
    fuente = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "fecha", "tipo", "ambito",
            "region_id", "locality_id", name="uq_calendar_mark_scope"
        ),
    )


class CalendarFeedStg(Base):
    """
    Staging opcional para importar festivos desde ICS/CSV.
    """
    __tablename__ = "calendar_feed_stg"

    id = Column(Integer, primary_key=True)
    raw = Column(Text, nullable=True)
    fecha = Column(Date, nullable=False, index=True)
    nombre = Column(String, nullable=False)
    tipo = Column(String, nullable=False, default="FESTIVO")
    ambito = Column(String, nullable=False)  # 'NACIONAL'|'AUTONOMICO'|'LOCAL'
    region_id = Column(Integer, ForeignKey("regions.id", ondelete="SET NULL"), index=True, nullable=True)
    locality_id = Column(Integer, ForeignKey("localities.id", ondelete="SET NULL"), index=True, nullable=True)
    fuente = Column(String, nullable=True)
    imported_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now()) 