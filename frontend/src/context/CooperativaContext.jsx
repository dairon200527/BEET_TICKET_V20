import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as adminService from '../services/adminService';
import { cooperativaScopeStore } from '../services/apiClient';
import { useAuth } from './AuthContext';

// A SUPER_ADMIN administers every cooperativa but must never see or touch
// more than one at a time — this context is the single source of truth
// for "which cooperativa is the SUPER_ADMIN currently operating on",
// mirrored into `cooperativaScopeStore` (services/apiClient.js) so every
// admin-scoped request automatically carries it as `?cooperativa_id=`.
//
// For ADMIN/LECTOR this context is inert: `isSuperAdmin` is false,
// `selected` is always null, and no selector should be rendered — those
// roles are always scoped server-side to their own `cooperativa_id`.

const CooperativaContext = createContext(null);

export function CooperativaProvider({ children }) {
  const { isAuthenticated, isCheckingSession, role, roles } = useAuth();
  const isSuperAdmin = isAuthenticated && role === roles.SUPER_ADMIN;

  const [cooperativas, setCooperativas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState(() => {
    const stored = cooperativaScopeStore.get();
    return stored ? Number(stored) : null;
  });

  const cargarCooperativas = useCallback(() => {
    setLoading(true);
    return adminService
      .listarCooperativas()
      .then((rows) => {
        setCooperativas(rows);
        return rows;
      })
      .catch(() => {
        setCooperativas([]);
        return [];
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    // While AuthContext is still verifying a stored token (e.g. right
    // after a page reload/navigation), `isAuthenticated` is momentarily
    // false even for a real SUPER_ADMIN session — do NOT treat that as
    // "not a SUPER_ADMIN" and wipe the persisted selection out from under
    // an in-flight page load.
    if (isCheckingSession) return;

    if (!isSuperAdmin) {
      // Genuinely not a SUPER_ADMIN right now (logged out, or a different
      // role) — this selection is meaningless and must never leak into
      // the next session on this browser tab.
      setCooperativas([]);
      setSelectedId(null);
      cooperativaScopeStore.clear();
      return;
    }
    cargarCooperativas();
  }, [isCheckingSession, isSuperAdmin, cargarCooperativas]);

  const seleccionar = useCallback((id) => {
    const numericId = id ? Number(id) : null;
    setSelectedId(numericId);
    if (numericId) cooperativaScopeStore.set(numericId);
    else cooperativaScopeStore.clear();
  }, []);

  const selected = useMemo(
    () => cooperativas.find((c) => c.id === selectedId) || null,
    [cooperativas, selectedId]
  );

  const value = useMemo(
    () => ({
      isSuperAdmin,
      cooperativas,
      loading,
      selectedId,
      selected,
      seleccionar,
      recargarCooperativas: cargarCooperativas,
      // ADMIN/LECTOR never need to pick — only a SUPER_ADMIN without a
      // selection yet is blocked from seeing/touching module data.
      necesitaSeleccion: isSuperAdmin && !selectedId,
    }),
    [isSuperAdmin, cooperativas, loading, selectedId, selected, seleccionar, cargarCooperativas]
  );

  return <CooperativaContext.Provider value={value}>{children}</CooperativaContext.Provider>;
}

export function useCooperativa() {
  const ctx = useContext(CooperativaContext);
  if (!ctx) throw new Error('useCooperativa must be used within CooperativaProvider');
  return ctx;
}
