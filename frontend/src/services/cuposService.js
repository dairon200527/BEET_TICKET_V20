import { apiClient } from "./apiClient";

export function miCupo() {
  return apiClient.get("/api/cupos/me", { tokenAudience: "afiliado" });
}

export function obtenerCupo(afiliadoId) {
  return apiClient.get(`/api/cupos/${afiliadoId}`, { tokenAudience: "admin" });
}

export function actualizarCupo(afiliadoId, payload) {
  return apiClient.patch(`/api/cupos/${afiliadoId}`, payload, { tokenAudience: "admin" });
}

export function asignacionMasivaCupo(payload) {
  return apiClient.post("/api/cupos/asignacion-masiva", payload, { tokenAudience: "admin" });
}
