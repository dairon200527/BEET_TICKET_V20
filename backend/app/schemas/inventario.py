from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EstadoUnidadInventario


class UnidadInventarioOut(BaseModel):
    id: int
    convenio_id: int
    codigo: str
    estado: EstadoUnidadInventario
    fecha_ingreso: datetime

    model_config = {"from_attributes": True}


class UnidadInventarioCreate(BaseModel):
    """One row of a bulk inventory upload. `codigo` must be globally
    unique — enforced at the DB level too."""

    codigo: str = Field(min_length=1, max_length=100)


class InventarioCargaRequest(BaseModel):
    convenio_id: int
    unidades: list[UnidadInventarioCreate] = Field(min_length=1, max_length=5000)


class InventarioCargaResultado(BaseModel):
    filas_validas: int
    filas_duplicadas: int
    filas_invalidas: int


class InventarioResumenOut(BaseModel):
    convenio_id: int
    total: int
    disponible: int
    bloqueada: int
    entregada: int
    redimida: int
    cancelada: int
    vencida: int


class BloqueoInventarioRequest(BaseModel):
    unidad_ids: list[int] = Field(min_length=1)
    motivo: str = Field(min_length=1, max_length=300)
