import { useAffiliateAuth } from '../context/AffiliateAuthContext';

// Thin accessor over the SHARED cupo state in AffiliateAuthContext — every
// consumer (PortalHeader's chip, MiCupo, PurchaseFlow) reads the same
// value, so a purchase's `refrescarCupo()` call updates all of them at
// once instead of each holding its own stale fetch-on-mount copy. See
// AffiliateAuthContext.jsx for why this can't be a private per-component
// fetch: PortalLayout mounts the header once for the whole portal
// session, so it would never see a change made on another screen.
export function useMiCupo() {
  const { cupo, cupoLoading, refrescarCupo } = useAffiliateAuth();
  return { cupo, loading: cupoLoading, refrescar: refrescarCupo };
}
