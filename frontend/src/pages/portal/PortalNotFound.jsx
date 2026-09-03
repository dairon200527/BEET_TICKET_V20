import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../components/ui/States';
import { IconAlertas } from '../../components/ui/Icons';

export default function PortalNotFound() {
  const navigate = useNavigate();
  return (
    <EmptyState
      icon={<IconAlertas color="var(--text-muted)" />}
      title="Página no encontrada"
      description="La sección que buscas no existe o fue movida."
      actionLabel="Volver al inicio"
      onAction={() => navigate('/portal')}
    />
  );
}
