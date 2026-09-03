import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as authService from '../services/authService';
import * as adminService from '../services/adminService';
import { adminTokenStore } from '../services/apiClient';
import { ROLES_DISPLAY } from '../utils/roles';

// Real auth: the JWT lives in adminTokenStore (see services/apiClient.js);
// `role`/`permissions` below are ALWAYS derived from the backend's
// authenticated response (AdminOut.rol), never from anything editable in
// the browser. There is no more mock session or mock user list here.

const ROLES = {
  SUPER_ADMIN: ROLES_DISPLAY.SUPER_ADMIN,
  ADMIN: ROLES_DISPLAY.ADMIN,
  LECTOR: ROLES_DISPLAY.LECTOR,
};

const PERMISSIONS = {
  [ROLES.SUPER_ADMIN]: { write: true, manageUsers: true, manageConfig: true },
  [ROLES.ADMIN]: { write: true, manageUsers: false, manageConfig: true },
  [ROLES.LECTOR]: { write: false, manageUsers: false, manageConfig: false },
};

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // 'checking' (verifying a stored token on load) | 'authenticated' | 'anonymous'
  const [status, setStatus] = useState('checking');
  const [adminUser, setAdminUser] = useState(null); // real AdminOut from the backend
  const [nombreEntidad, setNombreEntidad] = useState('');

  const loadCooperativa = useCallback(() => {
    adminService.obtenerCooperativa().then((c) => setNombreEntidad(c.nombre)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!adminTokenStore.get()) {
      setStatus('anonymous');
      return;
    }
    // A token was left in storage from a previous session — verify it's
    // still valid against the real backend before trusting it (it may
    // have expired, or the user may have been deactivated meanwhile).
    authService
      .getAdminMe()
      .then((usuario) => {
        setAdminUser(usuario);
        setStatus('authenticated');
        loadCooperativa();
      })
      .catch(() => {
        adminTokenStore.clear();
        setStatus('anonymous');
      });
  }, [loadCooperativa]);

  const login = useCallback(
    async (correo, password) => {
      const usuario = await authService.adminLogin(correo, password); // throws ApiError on 401/etc.
      setAdminUser(usuario);
      setStatus('authenticated');
      loadCooperativa();
      return usuario;
    },
    [loadCooperativa]
  );

  const logout = useCallback(() => {
    authService.adminLogout();
    setAdminUser(null);
    setNombreEntidad('');
    setStatus('anonymous');
  }, []);

  useEffect(() => {
    // Fired by services/apiClient.js whenever an admin-scoped request gets a
    // 401 (expired token, deactivated user, etc.) — reflect that immediately
    // instead of leaving stale "authenticated" UI around a dead session.
    const onSessionExpired = (e) => {
      if (e.detail?.tokenAudience === 'admin') logout();
    };
    window.addEventListener('beetticket:session-expired', onSessionExpired);
    return () => window.removeEventListener('beetticket:session-expired', onSessionExpired);
  }, [logout]);

  const role = adminUser ? ROLES_DISPLAY[adminUser.rol] ?? ROLES.LECTOR : ROLES.LECTOR;

  const value = useMemo(
    () => ({
      isAuthenticated: status === 'authenticated',
      isCheckingSession: status === 'checking',
      login,
      logout,
      role, // real, backend-authenticated role — see PermissionGate/Header for why this can no longer be changed from the UI
      roles: ROLES,
      permissions: PERMISSIONS[role],
      currentUser: adminUser ? { nombre: adminUser.nombre, correo: adminUser.correo, rol: role } : { nombre: '', correo: '', rol: role },
      nombreEntidad: nombreEntidad || 'tu cooperativa',
    }),
    [status, adminUser, role, nombreEntidad, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
