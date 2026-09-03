import { NavLink } from 'react-router-dom';
import { IconDashboard, IconGrid, IconCupos, IconAfiliados, IconRedencion } from '../ui/Icons';

const ITEMS = [
  { to: '/portal', label: 'Inicio', icon: IconDashboard, end: true },
  { to: '/portal/catalogo', label: 'Beneficios', icon: IconGrid },
  { to: '/portal/tickets', label: 'Tickets', icon: IconRedencion },
  { to: '/portal/cupo', label: 'Cupo', icon: IconCupos },
  { to: '/portal/perfil', label: 'Perfil', icon: IconAfiliados },
];

export default function PortalBottomNav() {
  return (
    <nav className="portal-bottom-nav">
      {ITEMS.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `portal-bottom-item ${isActive ? 'active' : ''}`}>
          <item.icon size={20} />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
