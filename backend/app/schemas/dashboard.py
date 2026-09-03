from decimal import Decimal

from pydantic import BaseModel


class VentasPorFormaDePago(BaseModel):
    tarjeta: Decimal
    cupo: Decimal
    pct_tarjeta: int
    pct_cupo: int


class DashboardStatsOut(BaseModel):
    """Always computed by scoping every underlying query to the
    authenticated admin's cooperativa_id — never a global figure.

    NOTE: `unidades_inventario` has no expiration date column in the real
    schema (unlike an earlier design assumption), so "units about to
    expire" is not derivable per-unit. `convenios_por_vencer` is the real
    equivalent — convenios whose `fecha_fin` is approaching."""

    ventas_del_mes: Decimal
    ahorro_generado: Decimal
    convenios_por_vencer: int
    convenios_activos: int
    ventas_por_forma_de_pago: VentasPorFormaDePago


class RendimientoConvenioOut(BaseModel):
    convenio_id: int
    convenio_nombre: str
    unidades_vendidas: int
    ingresos: Decimal
    disponible: int
    entregada: int
    tasa_redencion: int
