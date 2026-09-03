import { useAuth } from '../../context/AuthContext';
import { NoPermissionState } from './States';

// Wrap write-only UI (buttons, forms, actions) so the "Lector" role never
// sees affordances it can't use — per the functional spec's role rules.
export default function PermissionGate({ children, fallback = null }) {
  const { permissions } = useAuth();
  if (!permissions.write) return fallback;
  return children;
}

export function RequireWriteAccess({ children }) {
  const { permissions, nombreEntidad, role } = useAuth();
  if (!permissions.write) return <NoPermissionState nombreEntidad={nombreEntidad} role={role} />;
  return children;
}

export function RequireUserManagement({ children }) {
  const { permissions, nombreEntidad, role } = useAuth();
  if (!permissions.manageUsers) return <NoPermissionState nombreEntidad={nombreEntidad} role={role} />;
  return children;
}
