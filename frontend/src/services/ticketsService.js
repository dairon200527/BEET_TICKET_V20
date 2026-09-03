import { apiClient } from "./apiClient";

export function misTickets() {
  return apiClient.get("/api/tickets/me", { tokenAudience: "afiliado" });
}

// Returns a Blob (raw PDF bytes) — the backend serves the ticket PDF
// directly, not a JSON envelope with a download URL. Callers turn this
// into a browser-openable link via `URL.createObjectURL`.
export function descargarMiTicket(unidadId) {
  return apiClient.getBlob(`/api/tickets/me/${unidadId}/descarga`, { tokenAudience: "afiliado" });
}
