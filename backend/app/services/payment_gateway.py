"""
Payment gateway abstraction — TARJETA (card) payments only; CUPO
(credit-quota) payments never touch a gateway at all (see cupo_service.py).

This is a MOCK/sandbox implementation — no real provider (Wompi, PayU,
ePayco) is integrated yet, and this function makes no outbound network
call of any kind. The result is deterministic from the last 4 digits of
`numero_tarjeta`, so the affiliate portal's purchase flow can be exercised
end-to-end (including the rejection/error paths and their UI states)
before a real gateway exists. Swapping in a real provider later means
replacing the body of `procesar_pago_tarjeta` below with a real API call —
the call site (transaction_service.py) does not need to change, since it
only depends on this function's signature and the shape of `ResultadoPago`.

Test card numbers (any length ending in these 4 digits):
    ...0000  -> approved
    ...0001  -> declined, insufficient funds
    ...0002  -> declined, invalid/expired card
    ...0003  -> gateway error (simulated timeout)
    anything else -> approved (default, so ad-hoc testing isn't blocked)
"""
from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

ResultadoPagoTipo = Literal["aprobado", "rechazado_fondos", "rechazado_invalida", "error_pasarela"]

# Artificial network/processing latency, so the UI's "procesando pago"
# state is actually exercisable instead of resolving instantly. Tests
# monkeypatch this to (0, 0) to stay fast.
LATENCY_RANGE_SECONDS: tuple[float, float] = (1.0, 2.0)

_RESULTADOS: dict[str, tuple[bool, ResultadoPagoTipo, str | None]] = {
    "0000": (True, "aprobado", None),
    "0001": (False, "rechazado_fondos", "Pago rechazado: fondos insuficientes."),
    "0002": (False, "rechazado_invalida", "Pago rechazado: tarjeta inválida o vencida."),
    "0003": (False, "error_pasarela", "Error de la pasarela de pago (tiempo de espera agotado). Intenta nuevamente."),
}


@dataclass
class ResultadoPago:
    aprobado: bool
    tipo: ResultadoPagoTipo
    referencia: str | None
    motivo_rechazo: str | None = None


def procesar_pago_tarjeta(*, monto: Decimal, numero_tarjeta: str) -> ResultadoPago:
    """DEV/SANDBOX-ONLY mock gateway — see module docstring for the test
    card numbers this reacts to. `monto` is accepted (and would be sent to
    a real gateway) but doesn't affect the simulated outcome."""
    time.sleep(random.uniform(*LATENCY_RANGE_SECONDS))

    ultimos_4 = numero_tarjeta.strip()[-4:]
    aprobado, tipo, motivo = _RESULTADOS.get(ultimos_4, (True, "aprobado", None))

    if not aprobado:
        return ResultadoPago(aprobado=False, tipo=tipo, referencia=None, motivo_rechazo=motivo)
    return ResultadoPago(aprobado=True, tipo=tipo, referencia=f"MOCK-{uuid.uuid4().hex[:12].upper()}")
