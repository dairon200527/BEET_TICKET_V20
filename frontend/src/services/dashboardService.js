import { apiClient } from "./apiClient";

export function obtenerDashboardStats() {
  return apiClient.get("/api/dashboard/stats", { tokenAudience: "admin" });
}
