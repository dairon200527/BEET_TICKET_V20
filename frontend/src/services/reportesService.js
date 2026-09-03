import { apiClient } from "./apiClient";

export function obtenerRendimientoConvenios() {
  return apiClient.get("/api/reportes/rendimiento-convenios", { tokenAudience: "admin" });
}

// Both resolve to { blob, filename } — real .xlsx bytes, not JSON, with
// the server-generated dated filename (Content-Disposition) rather than
// one the frontend has to guess. See apiClient.getBlobWithFilename.
export function exportarRendimientoConvenios() {
  return apiClient.getBlobWithFilename("/api/reportes/rendimiento-convenios/exportar", { tokenAudience: "admin" }, "rendimiento_convenios.xlsx");
}

export function exportarAfiliados() {
  return apiClient.getBlobWithFilename("/api/reportes/afiliados/exportar", { tokenAudience: "admin" }, "afiliados.xlsx");
}
