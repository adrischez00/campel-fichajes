from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Date, Time, Text,
    func, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy import Enum as SAEnum, Numeric
import enum

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
    tipo = Column(String, nullable=False)
    # Aware + default en BD (UTC)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    hash = Column(String, nullable=False)
    is_manual = Column(Boolean, default=False)
    motivo = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    usuario = relationship("User", back_populates="fichajes")


class SolicitudManual(Base):
    __tablename__ = "solicitudes"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String, nullable=False)
    hora = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    motivo = Column(String, nullable=False)
    estado = Column(String, default="pendiente")
    # Aware + default en BD (UTC)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))

    usuario = relationship("User", back_populates="solicitudes")


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

# =========================
# Convenios, Reglas y Saldos de Ausencias
# =========================

class TipoAusenciaEnum(enum.Enum):
    VACACIONES = "VACACIONES"
    ASUNTOS_PROPIOS = "ASUNTOS_PROPIOS"
    BAJA = "BAJA"
    CITA_MEDICA = "CITA_MEDICA"
    OTRA = "OTRA"


class ComputoDiasEnum(enum.Enum):
    LABORABLES = "LABORABLES"
    NATURALES = "NATURALES"


class DevengoEnum(enum.Enum):
    ANUAL = "ANUAL"
    MENSUAL = "MENSUAL"


class Convenio(Base):
    __tablename__ = "convenios"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(120), unique=True, nullable=False, index=True)
    activo = Column(Boolean, default=True, nullable=False)

    reglas = relationship("ReglaAusencia", back_populates="convenio", cascade="all, delete-orphan")
    usuarios = relationship("UsuarioConvenio", back_populates="convenio", cascade="all, delete-orphan")


class ReglaAusencia(Base):
    __tablename__ = "reglas_ausencia"

    id = Column(Integer, primary_key=True)
    convenio_id = Column(Integer, ForeignKey("convenios.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(SAEnum(TipoAusenciaEnum), nullable=False, index=True)

    # Parámetros de la regla
    dias_anuales = Column(Numeric(5, 2), nullable=False)  # p.ej. 30.00
    computo = Column(SAEnum(ComputoDiasEnum), nullable=False, default=ComputoDiasEnum.LABORABLES)
    permite_mediodia = Column(Boolean, nullable=False, default=True)
    devengo = Column(SAEnum(DevengoEnum), nullable=False, default=DevengoEnum.ANUAL)
    arrastre_max_dias = Column(Numeric(5, 2), nullable=True)      # p.ej. 5.00
    caducidad_arrastre_mes = Column(Integer, nullable=True)       # p.ej. 3 (marzo => 31/03)

    convenio = relationship("Convenio", back_populates="reglas")

    __table_args__ = (
        UniqueConstraint("convenio_id", "tipo", name="uq_regla_convenio_tipo"),
    )


class UsuarioConvenio(Base):
    __tablename__ = "usuarios_convenio"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    convenio_id = Column(Integer, ForeignKey("convenios.id", ondelete="RESTRICT"), nullable=False, index=True)
    vigente_desde = Column(Date, nullable=False, index=True)
    vigente_hasta = Column(Date, nullable=True, index=True)

    usuario = relationship("User")
    convenio = relationship("Convenio", back_populates="usuarios")

    __table_args__ = (
        UniqueConstraint("usuario_id", "convenio_id", "vigente_desde", name="uq_usuario_convenio_desde"),
    )


class SaldoAusencia(Base):
    """
    Saldo anual por usuario + tipo de ausencia.
    disponible = asignado + arrastre - gastado
    """
    __tablename__ = "saldos_ausencia"

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(SAEnum(TipoAusenciaEnum), nullable=False, index=True)
    anio = Column(Integer, nullable=False, index=True)

    asignado = Column(Numeric(6, 2), nullable=False, default=0)  # total del año (regla + arrastre)
    arrastre = Column(Numeric(6, 2), nullable=False, default=0)  # carry-over aplicado
    gastado = Column(Numeric(6, 2), nullable=False, default=0)   # consumido por aprobaciones

    __table_args__ = (
        UniqueConstraint("usuario_id", "tipo", "anio", name="uq_saldo_usuario_tipo_anio"),
    )


class MotivoMovimientoEnum(enum.Enum):
    ASIGNACION = "ASIGNACION"   # + asignación anual o arrastre
    APROBACION = "APROBACION"   # - por aprobación de ausencia
    REVERSO = "REVERSO"         # + por anulación/revocación
    AJUSTE = "AJUSTE"           # +/- ajuste manual
    ARRASTRE = "ARRASTRE"       # + traspaso de días entre años


class MovimientoSaldoAusencia(Base):
    __tablename__ = "movimientos_saldo_ausencia"

    id = Column(Integer, primary_key=True)
    saldo_id = Column(Integer, ForeignKey("saldos_ausencia.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    delta = Column(Numeric(6, 2), nullable=False)  # negativo al consumir; positivo al revertir/asignar
    motivo = Column(SAEnum(MotivoMovimientoEnum), nullable=False, index=True)
    referencia = Column(String(50), nullable=True)  # p.ej. "ausencia:123" para auditoría

    saldo = relationship("SaldoAusencia")
