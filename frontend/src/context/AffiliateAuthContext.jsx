import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as authService from '../services/authService';
import * as afiliadosService from '../services/afiliadosService';
import * as cuposService from '../services/cuposService';
import { afiliadoTokenStore, ApiError } from '../services/apiClient';

// Real affiliate session — the JWT lives in afiliadoTokenStore (see
// services/apiClient.js), fully separate from the admin token. There is no
// role switcher here on purpose: a real affiliate never gets to pick who
// they are — identity and profile always come from the authenticated
// backend response, never from anything editable in the browser.

const AffiliateAuthContext = createContext(null);

export function AffiliateAuthProvider({ children }) {
  // 'checking' (verifying a stored token on load) | 'authenticated' | 'anonymous'
  const [status, setStatus] = useState('checking');
  const [afiliado, setAfiliado] = useState(null); // real AfiliadoOut from the backend

  // The affiliate's own credit quota, held HERE (not in a private hook per
  // consumer) precisely so every screen that shows it — the persistent
  // portal header's chip, "Mi cupo", the purchase flow — reads the SAME
  // value and updates together. PortalLayout mounts PortalHeader ONCE for
  // the whole portal session (nested routes render inside its <Outlet>),
  // so a header with its own private fetch-on-mount would never see a
  // cupo change from a purchase made on a different screen without a full
  // page reload — `refrescarCupo` is how a completed purchase fixes that.
  const [cupo, setCupo] = useState(null);
  const [cupoLoading, setCupoLoading] = useState(true);

  const refrescarCupo = useCallback(() => {
    setCupoLoading(true);
    return cuposService
      .miCupo()
      .then((c) => setCupo(c))
      .catch((err) => {
        if (!(err instanceof ApiError && err.status === 404)) {
          // eslint-disable-next-line no-console
          console.error('No se pudo cargar el cupo del afiliado', err);
        }
        setCupo(null);
      })
      .finally(() => setCupoLoading(false));
  }, []);

  useEffect(() => {
    if (!afiliadoTokenStore.get()) {
      setStatus('anonymous');
      return;
    }
    // A token was left in storage from a previous session — verify it's
    // still valid, and load the full profile (afiliadosService.miPerfilAfiliado
    // returns more fields than the login response, e.g. fecha_ingreso).
    afiliadosService
      .miPerfilAfiliado()
      .then((perfil) => {
        setAfiliado(perfil);
        setStatus('authenticated');
        refrescarCupo();
      })
      .catch(() => {
        afiliadoTokenStore.clear();
        setStatus('anonymous');
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (correo, password) => {
    await authService.afiliadoLogin(correo, password); // throws ApiError on 401/etc.
    const perfil = await afiliadosService.miPerfilAfiliado();
    setAfiliado(perfil);
    setStatus('authenticated');
    refrescarCupo();
    return perfil;
  }, [refrescarCupo]);

  const registro = useCallback(
    (documento, correo, password, confirmarPassword) =>
      authService.afiliadoRegistro(documento, correo, password, confirmarPassword), // returns a Message; no token — the affiliate still has to log in afterward
    []
  );

  const logout = useCallback(() => {
    authService.afiliadoLogout();
    setAfiliado(null);
    setStatus('anonymous');
    setCupo(null);
  }, []);

  const updateProfile = useCallback(async (patch) => {
    const actualizado = await afiliadosService.actualizarMiPerfilAfiliado(patch);
    setAfiliado(actualizado);
    return actualizado;
  }, []);

  useEffect(() => {
    const onSessionExpired = (e) => {
      if (e.detail?.tokenAudience === 'afiliado') logout();
    };
    window.addEventListener('beetticket:session-expired', onSessionExpired);
    return () => window.removeEventListener('beetticket:session-expired', onSessionExpired);
  }, [logout]);

  const value = useMemo(
    () => ({
      isAuthenticated: status === 'authenticated',
      isCheckingSession: status === 'checking',
      afiliado,
      login,
      registro,
      logout,
      updateProfile,
      cupo,
      cupoLoading,
      refrescarCupo,
    }),
    [status, afiliado, login, registro, logout, updateProfile, cupo, cupoLoading, refrescarCupo]
  );

  return <AffiliateAuthContext.Provider value={value}>{children}</AffiliateAuthContext.Provider>;
}

export function useAffiliateAuth() {
  const ctx = useContext(AffiliateAuthContext);
  if (!ctx) throw new Error('useAffiliateAuth must be used within AffiliateAuthProvider');
  return ctx;
}
