import { apiClient } from './apiClient';

// The 4 fixed, code-owned ticket designs — clave/nombre only, never any
// HTML/CSS. Pure code on the backend (no database row involved at all).
export function listarCatalogoPlantillas() {
  return apiClient.get('/api/plantillas/catalogo', { tokenAudience: 'admin' });
}

// A real PDF of the design (same rendering path a real ticket uses,
// with safe fixture data) — lets an admin preview each design.
export function previsualizarCatalogoPlantilla(clave) {
  return apiClient.getBlob(`/api/plantillas/catalogo/${clave}/preview`, { tokenAudience: 'admin' });
}

// The unified "Seleccionar plantilla" list for one convenio: the 4
// catalog designs PLUS every real per-convenio plantilla ever created
// for it, each carrying `en_uso` — the single item (across both kinds)
// that would actually be used for a real ticket right now.
export function listarPlantillasDisponibles(convenioId) {
  return apiClient.get(`/api/plantillas/disponibles?convenio_id=${convenioId}`, { tokenAudience: 'admin' });
}

// Real per-convenio plantillas created from pasted HTML/Jinja2 source —
// no visual editor, no manual positioning (see
// backend/app/services/template_engine.py's `validar_y_renderizar`,
// shared by both endpoints below so a preview can never look different
// from what actually gets saved). `formData` fields: convenio_id
// (required), html (required), nombre (optional).
export function previsualizarPlantillaHtml(formData) {
  return apiClient.postFormBlob('/api/plantillas/preview', formData, { tokenAudience: 'admin' });
}

export function crearPlantillaHtml(formData) {
  return apiClient.postForm('/api/plantillas', formData, { tokenAudience: 'admin' });
}

// A real PDF preview (fixture data) of a plantilla that already exists
// — used by "Ver muestra" on a personalizada item in the unified list.
export function previsualizarPlantillaPorId(plantillaId) {
  return apiClient.getBlob(`/api/plantillas/${plantillaId}/preview`, { tokenAudience: 'admin' });
}

// Activate (`estado: true` — becomes THE plantilla in effect, clearing
// any catalog selection and deactivating every sibling) or deactivate
// (`estado: false`, "Dejar de usar") a real per-convenio plantilla.
export function actualizarEstadoPlantilla(plantillaId, estado) {
  return apiClient.patch(`/api/plantillas/${plantillaId}`, { estado }, { tokenAudience: 'admin' });
}

// Permanently removes a real per-convenio plantilla (never a catalog
// design — those aren't rows and have no id). The row simply stops
// appearing in `listarPlantillasDisponibles`.
export function eliminarPlantilla(plantillaId) {
  return apiClient.delete(`/api/plantillas/${plantillaId}`, { tokenAudience: 'admin' });
}
