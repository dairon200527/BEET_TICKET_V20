// Single source of truth for mapping the backend's real role vocabulary
// (RolAdmin, in backend/app/models/enums.py: SUPER_ADMIN/ADMIN/LECTOR —
// uppercase, exactly matching the real database's usuarios_admin.rol CHECK
// constraint) to this UI's display labels. Used by AuthContext (to show
// the authenticated user's real role) and by UsuariosList (to send the
// backend-shaped value when creating/editing an admin user).
export const ROLES_DISPLAY = {
  SUPER_ADMIN: 'Súper administrador',
  ADMIN: 'Administrador',
  LECTOR: 'Lector',
};

export const ROLES_BACKEND = Object.fromEntries(Object.entries(ROLES_DISPLAY).map(([backend, display]) => [display, backend]));
