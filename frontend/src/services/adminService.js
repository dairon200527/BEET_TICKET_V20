import { apiClient } from "./apiClient";

// `cooperativaId` is only ever meaningful for a SUPER_ADMIN, who
// administers every cooperativa — omit it to list every usuario across
// all of them. `estado` (true/false) and `q` (free text — matches the
// usuario's nombre/correo OR its cooperativa's nombre) are both optional.
//
// `skipCooperativaScope: true` on every call in this section (usuarios +
// cooperativas management) is NOT optional to drop: these endpoints are
// cross-cooperativa by design (see app/routers/admin.py). Without it,
// apiClient silently injects whatever cooperativa a SUPER_ADMIN happens
// to have selected in the persistent header selector into the request —
// which would make a usuario belonging to any OTHER cooperativa (or a
// SUPER_ADMIN with no cooperativa at all) simply vanish from the list,
// looking exactly like the list "not refreshing" after a create/delete
// when in fact the row was never fetched at all.
export function listarUsuariosAdmin(cooperativaId, { estado, q } = {}) {
  const params = new URLSearchParams();
  if (cooperativaId) params.set("cooperativa_id", cooperativaId);
  if (estado !== undefined && estado !== null && estado !== "") params.set("estado", estado);
  if (q) params.set("q", q);
  const query = params.toString();
  return apiClient.get(`/api/admin/usuarios${query ? `?${query}` : ""}`, { tokenAudience: "admin", skipCooperativaScope: true });
}

export function crearUsuarioAdmin(payload) {
  return apiClient.post("/api/admin/usuarios", payload, { tokenAudience: "admin", skipCooperativaScope: true });
}

export function actualizarUsuarioAdmin(id, payload) {
  return apiClient.patch(`/api/admin/usuarios/${id}`, payload, { tokenAudience: "admin", skipCooperativaScope: true });
}

// Real, permanent DELETE — distinct from actualizarUsuarioAdmin(id, {estado:
// false}), which only revokes access while keeping the row (and its audit
// history) intact. Resolves with no body (204 No Content) on success.
export function eliminarUsuarioAdmin(id) {
  return apiClient.delete(`/api/admin/usuarios/${id}`, { tokenAudience: "admin", skipCooperativaScope: true });
}

// Bare list of every cooperativa (id/nombre/estado only) — used to
// populate the cooperativa selector/filter on the usuarios screen.
export function listarCooperativas() {
  return apiClient.get("/api/admin/cooperativas", { tokenAudience: "admin", skipCooperativaScope: true });
}

export function crearCooperativa(payload) {
  return apiClient.post("/api/admin/cooperativas", payload, { tokenAudience: "admin", skipCooperativaScope: true });
}

export function obtenerCooperativa() {
  return apiClient.get("/api/admin/cooperativa", { tokenAudience: "admin" });
}

export function actualizarCooperativa(payload) {
  return apiClient.patch("/api/admin/cooperativa", payload, { tokenAudience: "admin" });
}

export function listarLogsAuditoria({ page = 1, pageSize = 50 } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  return apiClient.get(`/api/admin/logs?${params.toString()}`, { tokenAudience: "admin" });
}
