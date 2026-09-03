from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import EstadoTransaccion, MetodoPago


class CompraRequest(BaseModel):
    """The purchase request body. `afiliado_id` is intentionally ABSENT —
    the purchasing affiliate is always the one derived from the JWT (see
    dependencies/auth.get_current_affiliate), never a client-supplied id.

    `firma_base64` is required for cupo purchases (raw base64 PNG, no
    data-URL prefix) and captured in the same request as the purchase
    itself — this is what lets transaction_service.py generate the debt-
    assumption document as one more step of the SAME atomic database
    transaction, instead of leaving inventory/cupo mutated while a
    signature is still pending.

    `numero_tarjeta` is required for `metodo_pago=TARJETA` and drives the
    sandbox payment gateway's simulated outcome by its last 4 digits (see
    services/payment_gateway.py) — there is no real card network involved
    yet, so this is never sent anywhere outside this process."""

    convenio_id: int
    cantidad: int = Field(gt=0, le=50)
    metodo_pago: MetodoPago
    numero_cuotas: int | None = Field(default=None, gt=0, le=48)
    firma_base64: str | None = Field(default=None, min_length=10)
    numero_tarjeta: str | None = Field(default=None, min_length=4, max_length=32)

    @model_validator(mode="after")
    def cuotas_y_firma_solo_con_cupo(self) -> "CompraRequest":
        if self.metodo_pago == MetodoPago.CUPO and not self.numero_cuotas:
            raise ValueError("Debes indicar el número de cuotas para pagar con cupo.")
        if self.metodo_pago == MetodoPago.TARJETA and self.numero_cuotas:
            raise ValueError("Las cuotas solo aplican al pago con cupo.")
        if self.metodo_pago == MetodoPago.CUPO and not self.firma_base64:
            raise ValueError("Se requiere la firma para compras con cupo.")
        if self.metodo_pago == MetodoPago.TARJETA and self.firma_base64:
            raise ValueError("La firma solo aplica al pago con cupo.")
        if self.metodo_pago == MetodoPago.TARJETA and not self.numero_tarjeta:
            raise ValueError("Se requiere el número de tarjeta para pagar con tarjeta.")
        if self.metodo_pago == MetodoPago.CUPO and self.numero_tarjeta:
            raise ValueError("El número de tarjeta solo aplica al pago con tarjeta.")
        return self


class TransaccionOut(BaseModel):
    id: int
    afiliado_id: int
    convenio_id: int
    cantidad: int
    subtotal: Decimal
    total: Decimal
    metodo_pago: MetodoPago
    numero_cuotas: int | None
    estado: EstadoTransaccion
    referencia_pago: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransaccionDetalleOut(TransaccionOut):
    codigos: list[str] = []
    # Populated only on the immediate response to POST /transacciones/comprar
    # for a TARJETA payment that didn't come back "aprobado" — not
    # persisted anywhere (transacciones has no such column), since the
    # frontend only needs this to react right after the attempt it just
    # made. `resultado_pago` is the stable machine-readable outcome the UI
    # switches on; `motivo_rechazo` is the human-readable message.
    resultado_pago: str | None = None
    motivo_rechazo: str | None = None
