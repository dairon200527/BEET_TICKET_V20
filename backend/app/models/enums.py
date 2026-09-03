"""
Canonical state/role vocabularies — kept in sync EXACTLY with the CHECK
constraints in the real, provided PostgreSQL schema (see
../../../SCHEMA_NOTES.md for the full column-by-column comparison against
the earlier, incorrect assumption this backend originally shipped with).

Several `estado` columns that used to be modeled as string enums here are
now plain PostgreSQL booleans in the real schema (cooperativas, afiliados,
convenios, cupos_credito, usuarios_admin, plantillas) — those are typed as
`bool` directly on the models, not enums, and have no class here.
"""
import enum


class RolAdmin(str, enum.Enum):
    """usuarios_admin.rol CHECK constraint — uppercase, exactly these three."""

    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    LECTOR = "LECTOR"


class EstadoUnidadInventario(str, enum.Enum):
    """unidades_inventario.estado CHECK constraint — six lowercase states."""

    DISPONIBLE = "disponible"
    BLOQUEADA = "bloqueada"
    ENTREGADA = "entregada"
    REDIMIDA = "redimida"
    CANCELADA = "cancelada"
    VENCIDA = "vencida"


class EstadoTransaccion(str, enum.Enum):
    """transacciones.estado CHECK constraint — uppercase. Unlike an earlier
    design assumption, the real schema DOES include CANCELADA at the
    transaction level (in addition to unit-level cancellation)."""

    PENDIENTE = "PENDIENTE"
    APROBADA = "APROBADA"
    RECHAZADA = "RECHAZADA"
    CANCELADA = "CANCELADA"
    COMPLETADA = "COMPLETADA"


class EstadoTransaccionUnidad(str, enum.Enum):
    """transaccion_unidades.estado CHECK constraint — the per-unit
    fulfillment state within one transaction, separate from the unit's own
    lifecycle state in unidades_inventario.estado."""

    ASIGNADA = "ASIGNADA"
    ENTREGADA = "ENTREGADA"
    UTILIZADA = "UTILIZADA"
    CANCELADA = "CANCELADA"


class MetodoPago(str, enum.Enum):
    """transacciones.metodo_pago CHECK constraint — uppercase."""

    TARJETA = "TARJETA"
    CUPO = "CUPO"


class EstadoDocumento(str, enum.Enum):
    """documentos_asuncion_deuda.estado CHECK constraint — uppercase."""

    PENDIENTE = "PENDIENTE"
    FIRMADO = "FIRMADO"
    CANCELADO = "CANCELADO"
