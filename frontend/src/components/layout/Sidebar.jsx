import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import logo from '../../assets/logo-beet-ticket.svg';
import {
  IconDashboard, IconConvenios, IconInventario, IconAfiliados, IconCupos,
  IconVentas, IconReportes, IconAfiliados as IconUsers, IconConfiguracion,
  IconDocumentos,
} from '../ui/Icons';
import { useAuth } from '../../context/AuthContext';
import * as dashboardService from '../../services/dashboardService';

const NAV = [
  { to: '/', label: 'Dashboard', icon: IconDashboard, end: true },
  { to: '/convenios', label: 'Convenios', icon: IconConvenios },
  { to: '/inventario', label: 'Inventario', icon: IconInventario, badgeKey: 'inventario' },
  { to: '/afiliados', label: 'Afiliados', icon: IconAfiliados },
  { to: '/cupos', label: 'Cupos de crédito', icon: IconCupos },
  { to: '/transacciones', label: 'Transacciones', icon: IconVentas },
  { to: '/reportes', label: 'Reportes', icon: IconReportes },
  { to: '/usuarios', label: 'Usuarios', icon: IconUsers, requires: 'manageUsers' },
  { to: '/documentos-legales', label: 'Documentos legales', icon: IconDocumentos },
  { to: '/configuracion', label: 'Configuración', icon: IconConfiguracion },
];

export default function Sidebar({ mobileOpen, onCloseMobile }) {
  const { permissions } = useAuth();
  const [proximasAVencer, setProximasAVencer] = useState(0);

  useEffect(() => {
    // No badge shown until this resolves — 0 is a real "unknown yet" state,
    // never a fabricated placeholder count.
    dashboardService.obtenerDashboardStats().then((s) => setProximasAVencer(s.unidades_proximas_a_vencer)).catch(() => {});
  }, []);

  return (
    <>
      {mobileOpen && <div className="sidebar-scrim" onClick={onCloseMobile} />}
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <img src={logo} alt="BEET Ticket" height={40} />
        </div>
        <nav className="sidebar-nav">
          {NAV.filter((item) => !item.requires || permissions[item.requires]).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onCloseMobile}
              className={({ isActive }) => `sidebar-item ${isActive ? 'active' : ''}`}
            >
              <item.icon size={18} color={undefined} />
              <span>{item.label}</span>
              {item.badgeKey === 'inventario' && proximasAVencer > 0 && (
                <span className="sidebar-badge">{proximasAVencer}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer text-caption">v1.0 · Panel administrativo</div>
      </aside>
    </>
  );
}
