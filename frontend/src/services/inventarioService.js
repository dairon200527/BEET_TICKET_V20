import { apiClient } from "./apiClient";

export function listarInventario(convenioId, { estado, page = 1, pageSize = 50 } = {}) {
  const params = new URLSearchParams({ convenio_id: convenioId, page, page_size: pageSize });
  if (estado) params.set("estado", estado);
  return apiClient.get(`/api/inventario?${params.toString()}`, { tokenAudience: "admin" });
}

export function resumenInventario(convenioId) {
  return apiClient.get(`/api/inventario/resumen?convenio_id=${convenioId}`, { tokenAudience: "admin" });
}

export function cargaInventario(convenioId, file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.postForm(`/api/inventario/carga?convenio_id=${convenioId}`, formData, { tokenAudience: "admin" });
}

// Unlike cargaInventario above (codes for one already-selected convenio),
// this loads codes for MULTIPLE convenios in one file — each row names
// its own convenio by nombre. See backend/templates/plantilla_inventario.xlsx.
export function cargaMasivaInventario(file) {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.postForm("/api/inventario/carga-masiva", formData, { tokenAudience: "admin" });
}

export function bloquearUnidades(unidad_ids, motivo) {
  return apiClient.post("/api/inventario/bloquear", { unidad_ids, motivo }, { tokenAudience: "admin" });
}

export function desbloquearUnidades(unidad_ids, motivo) {
  return apiClient.post("/api/inventario/desbloquear", { unidad_ids, motivo }, { tokenAudience: "admin" });
}
