import { apiClient } from "./apiClient";

// `firma_base64` is required by the backend for metodo_pago === "CUPO"
// (raw base64, no data-URL prefix) — see backend/README.md.
// `metodo_pago` must be the uppercase value the backend's CHECK
// constraint/enum expects ("TARJETA" | "CUPO"), and cuotas travels as
// `numero_cuotas` (see backend/app/schemas/transaccion.py CompraRequest).
// `numero_tarjeta` is required for TARJETA — it drives the sandbox
// gateway's simulated outcome by its last 4 digits (see
// backend/app/services/payment_gateway.py); never sent for CUPO.
export function comprar({ convenio_id, cantidad, metodo_pago, numero_cuotas, firma_base64, numero_tarjeta }) {
  return apiClient.post(
    "/api/transacciones/comprar",
    {
      convenio_id,
      cantidad,
      metodo_pago: String(metodo_pago).toUpperCase(),
      numero_cuotas: numero_cuotas ?? null,
      firma_base64: firma_base64 ?? null,
      numero_tarjeta: numero_tarjeta ?? null,
    },
    { tokenAudience: "afiliado" }
  );
}

export function misTransacciones({ page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  return apiClient.get(`/api/transacciones/me?${params.toString()}`, { tokenAudience: "afiliado" });
}

export function miTransaccion(id) {
  return apiClient.get(`/api/transacciones/me/${id}`, { tokenAudience: "afiliado" });
}

export function listarTransacciones({ page = 1, pageSize = 20, estado } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (estado) params.set("estado", estado);
  return apiClient.get(`/api/transacciones?${params.toString()}`, { tokenAudience: "admin" });
}

export function obtenerTransaccion(id) {
  return apiClient.get(`/api/transacciones/${id}`, { tokenAudience: "admin" });
}
