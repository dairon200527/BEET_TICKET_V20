import { Outlet } from 'react-router-dom';
import PortalHeader from './PortalHeader';
import PortalBottomNav from './PortalBottomNav';

export default function PortalLayout() {
  return (
    <div className="portal-shell">
      <PortalHeader />
      <main className="portal-content">
        <Outlet />
      </main>
      <PortalBottomNav />
    </div>
  );
}
