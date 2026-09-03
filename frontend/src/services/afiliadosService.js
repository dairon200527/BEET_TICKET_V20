import { apiClient } from "./apiClient";

export function listarAfiliados({ page = 1, pageSize = 20, sortBy, estado, q } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (sortBy) params.set("sort_by", sortBy);
  if (estado) params.set("estado", estado);
  if (q) params.set("q", q);
  return apiClient.get(`/api/afiliados?${params.toString()}`, { tokenAudience: "admin" });
}

export function obtenerAfiliado(id) {
  return apiClient.get(`/api/afiliados/${id}`, { tokenAudience: "admin" });
}

export function crearAfiliado(payload) {
  return apiClient.post("/api/afiliados", payload, { tokenAudience: "admin" });
}

export function actualizarAfiliado(id, payload) {
  return apiClient.patch(`/api/afiliados/${id}`, payload, { tokenAudience: "admin" });
}

export function cargaMasivaAfiliados(file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.postForm("/api/afiliados/carga-masiva", formData, { tokenAudience: "admin" });
}

export function miPerfilAfiliado() {
  return apiClient.get("/api/afiliados/me", { tokenAudience: "afiliado" });
}

export function actualizarMiPerfilAfiliado(payload) {
  return apiClient.patch("/api/afiliados/me", payload, { tokenAudience: "afiliado" });
}
