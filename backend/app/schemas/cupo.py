from decimal import Decimal

from pydantic import BaseModel, Field


class CupoCreditoOut(BaseModel):
    id: int
    afiliado_id: int
    cupo_total: Decimal
    cupo_disponible: Decimal
    estado: bool

    model_config = {"from_attributes": True}


class CupoCreditoUpdate(BaseModel):
    cupo_total: Decimal | None = Field(default=None, ge=0)
    cupo_disponible: Decimal | None = Field(default=None, ge=0)
    estado: bool | None = None


class CupoAsignacionMasivaRequest(BaseModel):
    afiliado_ids: list[int] = Field(min_length=1)
    cupo_total: Decimal = Field(ge=0)
