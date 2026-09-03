from pydantic import BaseModel

from app.models.enums import EstadoUnidadInventario


class TicketOut(BaseModel):
    """A ticket, from the affiliate's point of view — one issued
    unidad_inventario belonging to one of their own transactions. NOTE:
    unlike an earlier design assumption, `unidades_inventario` has no
    `fecha_vencimiento` column in the real schema — there is no per-unit
    expiration date to show."""

    id: int
    codigo: str
    convenio_id: int
    transaccion_id: int
    estado: EstadoUnidadInventario

    model_config = {"from_attributes": True}
