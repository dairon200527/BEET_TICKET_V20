import { Navigate } from 'react-router-dom';
import { useAffiliateAuth } from '../../context/AffiliateAuthContext';
import { LoadingState } from '../ui/States';

export default function RequireAffiliateAuth({ children }) {
  const { isAuthenticated, isCheckingSession } = useAffiliateAuth();
  if (isCheckingSession) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '15vh' }}>
        <LoadingState title="Verificando sesión…" />
      </div>
    );
  }
  if (!isAuthenticated) return <Navigate to="/portal/login" replace />;
  return children;
}
