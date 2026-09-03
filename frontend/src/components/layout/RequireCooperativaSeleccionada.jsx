import { useCooperativa } from '../../context/CooperativaContext';
import { EmptyState } from '../ui/States';
import { IconInbox } from '../ui/Icons';

// Guards the 7 cooperativa-scoped admin screens (Dashboard, Convenios,
// Inventario, Afiliados, Cupos, Transacciones, Reportes): a SUPER_ADMIN
// must explicitly pick a cooperativa (selector in Header.jsx) before
// seeing or touching any of their data — never a default/first
// cooperativa, never mixed data. ADMIN/LECTOR never hit this (they are
// always scoped to their own cooperativa) — `necesitaSeleccion` is
// always false for them.
export default function RequireCooperativaSeleccionada({ children }) {
  const { necesitaSeleccion } = useCooperativa();

  if (necesitaSeleccion) {
    return (
      <EmptyState
        icon={<IconInbox color="var(--text-muted)" />}
        title="Selecciona una cooperativa"
        description="Selecciona una cooperativa arriba para ver esta información."
      />
    );
  }

  return children;
}
