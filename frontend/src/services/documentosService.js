import { apiClient } from "./apiClient";

export function misDocumentos({ page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  return apiClient.get(`/api/documentos/me?${params.toString()}`, { tokenAudience: "afiliado" });
}

export function descargarMiDocumento(id) {
  return apiClient.getBlob(`/api/documentos/me/${id}/descarga`, { tokenAudience: "afiliado" });
}

export function listarDocumentos({ page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams({ page, page_size: pageSize });
  return apiClient.get(`/api/documentos?${params.toString()}`, { tokenAudience: "admin" });
}

// Dispute support: every documento-legal signed by one affiliate,
// searched by `documento` (cédula) — `nombres` is only an extra
// confirmation the backend echoes back as `nombre_coincide`, never a
// second filter (see app/routers/documentos.py).
export function buscarDocumentosLegales({ documento, nombres }) {
  const params = new URLSearchParams({ documento });
  if (nombres && nombres.trim()) params.set("nombres", nombres.trim());
  return apiClient.get(`/api/documentos/legales/buscar?${params.toString()}`, { tokenAudience: "admin" });
}

export function descargarDocumento(id) {
  return apiClient.getBlob(`/api/documentos/${id}/descarga`, { tokenAudience: "admin" });
}
