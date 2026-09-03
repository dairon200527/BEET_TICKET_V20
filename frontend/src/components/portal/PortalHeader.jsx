import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import logo from '../../assets/logo-beet-ticket.svg';
import { useAffiliateAuth } from '../../context/AffiliateAuthContext';
import Avatar from '../ui/Avatar';
import { Dropdown } from '../ui/Nav';
import { ConfirmDialog } from '../ui/Modal';
import { IconLogout } from '../ui/Icons';
import { formatCOP } from '../../utils/format';
import { useMiCupo } from '../../hooks/useMiCupo';

const NAV_LINKS = [
  { to: '/portal', label: 'Inicio', end: true },
  { to: '/portal/catalogo', label: 'Beneficios' },
  { to: '/portal/tickets', label: 'Mis tickets' },
  { to: '/portal/cupo', label: 'Mi cupo' },
  { to: '/portal/perfil', label: 'Mi perfil' },
];

export default function PortalHeader() {
  const { afiliado, logout } = useAffiliateAuth();
  const { cupo } = useMiCupo();
  const navigate = useNavigate();
  const [profileOpen, setProfileOpen] = useState(false);
  const [confirmLogoutOpen, setConfirmLogoutOpen] = useState(false);

  const nombreCompleto = afiliado ? `${afiliado.nombres} ${afiliado.apellidos}` : '';
  const confirmarCierreSesion = () => { logout(); navigate('/portal/login'); };

  return (
    <header className="portal-header">
      <div className="portal-header-inner">
        <NavLink to="/portal" className="portal-logo">
          <img src={logo} alt="BEET Ticket" height={34} />
        </NavLink>

        <nav className="portal-header-nav">
          {NAV_LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => `portal-nav-link ${isActive ? 'active' : ''}`}>
              {l.label}
            </NavLink>
          ))}
        </nav>

        <div className="portal-header-right">
          {cupo && (
            <span className="portal-cupo-chip" title="Cupo de crédito disponible">
              Cupo: {formatCOP(cupo.cupo_disponible)}
            </span>
          )}

          <div style={{ position: 'relative' }}>
            <button className="profile-trigger" onClick={() => setProfileOpen((v) => !v)}>
              <Avatar name={nombreCompleto} size="sm" />
              <span className="profile-name">{nombreCompleto}</span>
            </button>
            <Dropdown
              open={profileOpen}
              onClose={() => setProfileOpen(false)}
              style={{ top: 46, right: 0 }}
              items={[
                { label: 'Mi perfil', onClick: () => navigate('/portal/perfil') },
                { label: 'Mis tickets', onClick: () => navigate('/portal/tickets') },
                { label: 'Mi cupo', onClick: () => navigate('/portal/cupo') },
                { divider: true },
                { label: 'Cerrar sesión', danger: true, onClick: () => setConfirmLogoutOpen(true) },
              ]}
            />
          </div>

          <button
            className="btn-icon"
            aria-label="Cerrar sesión"
            title="Cerrar sesión"
            onClick={() => setConfirmLogoutOpen(true)}
          >
            <IconLogout color="var(--text-primary)" />
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmLogoutOpen}
        onClose={() => setConfirmLogoutOpen(false)}
        onConfirm={confirmarCierreSesion}
        title="¿Cerrar sesión?"
        description="Vas a salir del portal del afiliado. Tendrás que volver a iniciar sesión para continuar."
        confirmLabel="Cerrar sesión"
      />
    </header>
  );
}
