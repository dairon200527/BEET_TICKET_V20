import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useCooperativa } from '../../context/CooperativaContext';
import { Breadcrumbs, Dropdown } from '../ui/Nav';
import { Select } from '../ui/Field';
import Avatar from '../ui/Avatar';
import { ConfirmDialog } from '../ui/Modal';
import { IconBell, IconLogout } from '../ui/Icons';
import { RoleBadge } from '../ui/Badge';
import { formatDateTime } from '../../utils/format';
import { useRecentActivity } from '../../hooks/useRecentActivity';

export default function Header({ breadcrumbs, onOpenMobileNav }) {
  const { currentUser, role, nombreEntidad, logout } = useAuth();
  const { isSuperAdmin, cooperativas, selected, selectedId, seleccionar } = useCooperativa();
  const [profileOpen, setProfileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [confirmLogoutOpen, setConfirmLogoutOpen] = useState(false);
  const navigate = useNavigate();
  const { items: actividadReciente } = useRecentActivity(5);

  const confirmarCierreSesion = () => { logout(); navigate('/login'); };

  return (
    <header className="app-header">
      <button className="mobile-nav-toggle" onClick={onOpenMobileNav} aria-label="Abrir menú">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="#1F2937" strokeWidth="1.6" strokeLinecap="round"><path d="M3 5.5h14M3 10h14M3 14.5h14" /></svg>
      </button>

      <div className="app-header-left">
        {breadcrumbs && <Breadcrumbs items={breadcrumbs} />}
      </div>

      <div className="app-header-right">
        {/* Persistent cooperativa selector — SUPER_ADMIN only. ADMIN/LECTOR
            are always scoped server-side to their own cooperativa and
            never see this control (see CooperativaContext). */}
        {isSuperAdmin && (
          <Select
            aria-label="Cooperativa seleccionada"
            value={selectedId ?? ''}
            onChange={(e) => seleccionar(e.target.value || null)}
            style={{ minWidth: 200 }}
          >
            <option value="">Selecciona una cooperativa…</option>
            {cooperativas.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}{!c.estado ? ' (inactiva)' : ''}</option>
            ))}
          </Select>
        )}

        {/* Real, backend-authenticated role — read-only display, not a
            switcher. There is no client-side mechanism to change it. */}
        <div title="Rol autenticado en el backend">
          <RoleBadge role={role} />
        </div>

        <div style={{ position: 'relative' }}>
          <button className="btn-icon" aria-label="Notificaciones" onClick={() => setNotifOpen((v) => !v)}>
            <IconBell color="var(--text-primary)" />
            {actividadReciente.length > 0 && <span className="header-dot" />}
          </button>
          {notifOpen && (
            <>
              <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setNotifOpen(false)} />
              <div className="dropdown-menu notif-panel" style={{ position: 'absolute', top: 46, right: 0, width: 320, zIndex: 41 }}>
                <div className="notif-header">Actividad reciente</div>
                {actividadReciente.length === 0 ? (
                  <div className="notif-item text-caption">Sin actividad registrada todavía.</div>
                ) : (
                  actividadReciente.map((a) => (
                    <div key={a.id} className="notif-item">
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{a.texto}</div>
                      <div className="text-caption">{a.detalle} · {formatDateTime(a.fecha)}</div>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>

        <div style={{ position: 'relative' }}>
          <button className="profile-trigger" onClick={() => setProfileOpen((v) => !v)}>
            <Avatar name={currentUser.nombre} size="sm" />
            <span className="profile-name">{currentUser.nombre}</span>
          </button>
          <Dropdown
            open={profileOpen}
            onClose={() => setProfileOpen(false)}
            style={{ top: 46, right: 0 }}
            items={[
              { label: isSuperAdmin ? selected?.nombre || 'Selecciona una cooperativa arriba' : nombreEntidad, disabled: true },
              { divider: true },
              { label: 'Mi perfil', onClick: () => navigate('/configuracion') },
              { label: 'Configuración', onClick: () => navigate('/configuracion') },
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

      <ConfirmDialog
        open={confirmLogoutOpen}
        onClose={() => setConfirmLogoutOpen(false)}
        onConfirm={confirmarCierreSesion}
        title="¿Cerrar sesión?"
        description="Vas a salir del panel administrativo. Tendrás que volver a iniciar sesión para continuar."
        confirmLabel="Cerrar sesión"
      />
    </header>
  );
}
