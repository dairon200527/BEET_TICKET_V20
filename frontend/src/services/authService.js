// Real admin + affiliate authentication against the FastAPI backend.
// See ./README.md — not yet wired into AuthContext/AffiliateAuthContext.
import { adminTokenStore, afiliadoTokenStore, apiClient } from "./apiClient";

export async function adminLogin(correo, password) {
  const data = await apiClient.post("/api/auth/admin/login", { correo, password });
  adminTokenStore.set(data.access_token);
  return data.usuario;
}

export function adminLogout() {
  adminTokenStore.clear();
}

export function getAdminMe() {
  return apiClient.get("/api/auth/admin/me", { tokenAudience: "admin" });
}

export function adminForgotPassword(identificador) {
  return apiClient.post("/api/auth/admin/forgot-password", { identificador });
}

export function adminResetPassword(token, nueva_password, confirmar_password) {
  return apiClient.post("/api/auth/admin/reset-password", { token, nueva_password, confirmar_password });
}

export async function afiliadoLogin(correo, password) {
  const data = await apiClient.post("/api/auth/afiliado/login", { correo, password });
  afiliadoTokenStore.set(data.access_token);
  return data.afiliado;
}

export function afiliadoLogout() {
  afiliadoTokenStore.clear();
}

// `documento`+`correo` together identify the roster row an admin already
// loaded (documento alone is only unique per-cooperativa) — see
// backend/app/routers/auth_afiliado.py. There is no `acepta_terminos`
// column on the backend; the checkbox is enforced client-side only (see
// PortalRegister.jsx) and never sent to the API.
export function afiliadoRegistro(documento, correo, password, confirmar_password) {
  return apiClient.post("/api/auth/afiliado/registro", { documento, correo, password, confirmar_password });
}

export function getAfiliadoMe() {
  return apiClient.get("/api/auth/afiliado/me", { tokenAudience: "afiliado" });
}

export function afiliadoForgotPassword(identificador) {
  return apiClient.post("/api/auth/afiliado/forgot-password", { identificador });
}

export function afiliadoResetPassword(token, nueva_password, confirmar_password) {
  return apiClient.post("/api/auth/afiliado/reset-password", { token, nueva_password, confirmar_password });
}
