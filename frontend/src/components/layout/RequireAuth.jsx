import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LoadingState } from '../ui/States';

export default function RequireAuth({ children, fallback }) {
  const { isAuthenticated, isCheckingSession } = useAuth();
  if (isCheckingSession) {
    // Verifying a stored token against the real backend before deciding
    // whether to redirect to /login — avoids a login-page flash on reload.
    return (
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: '15vh' }}>
        <LoadingState title="Verificando sesión…" />
      </div>
    );
  }
  if (!isAuthenticated) return fallback ?? <Navigate to="/login" replace />;
  return children;
}
