import { Routes, Route } from 'react-router-dom';
import AdminLayout from './components/layout/AdminLayout';
import RequireAuth from './components/layout/RequireAuth';
import Login from './pages/Login';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import ConveniosList from './pages/admin/convenios/ConveniosList';
import ConvenioForm from './pages/admin/convenios/ConvenioForm';
import ConvenioDetail from './pages/admin/convenios/ConvenioDetail';
import InventarioGeneral from './pages/admin/inventario/InventarioGeneral';
import InventarioConvenio from './pages/admin/inventario/InventarioConvenio';
import AfiliadosList from './pages/admin/afiliados/AfiliadosList';
import AfiliadoDetail from './pages/admin/afiliados/AfiliadoDetail';
import CuposList from './pages/admin/cupos/CuposList';
import TransaccionesList from './pages/admin/transacciones/TransaccionesList';
import TransaccionDetail from './pages/admin/transacciones/TransaccionDetail';
import Reportes from './pages/admin/reportes/Reportes';
import UsuariosList from './pages/admin/usuarios/UsuariosList';
import Configuracion from './pages/admin/configuracion/Configuracion';
import DocumentosLegales from './pages/admin/documentos/DocumentosLegales';
import NotFound from './pages/NotFound';
import RequireAffiliateAuth from './components/layout/RequireAffiliateAuth';
import PortalLayout from './components/portal/PortalLayout';
import PortalLogin from './pages/portal/PortalLogin';
import PortalHome from './pages/portal/PortalHome';
import Catalogo from './pages/portal/Catalogo';
import BenefitDetail from './pages/portal/BenefitDetail';
import Profile from './pages/portal/Profile';
import MiCupo from './pages/portal/MiCupo';
import PortalRegister from './pages/portal/PortalRegister';
import PurchaseFlow from './pages/portal/PurchaseFlow';
import MyTickets from './pages/portal/MyTickets';
import TicketDetail from './pages/portal/TicketDetail';
import EditProfile from './pages/portal/EditProfile';
import PortalNotFound from './pages/portal/PortalNotFound';

// NOT routed yet — the debt-assumption document (generated during a cupo
// purchase, see backend/app/services/transaction_service.py) has no
// affiliate-facing download endpoint mounted this pass (only the ticket
// PDF does, via /api/tickets/me/{id}/descarga). Their page files still
// exist in pages/portal/ as scaffolding for a future pass — see
// frontend/README.md.
// import MyDocuments from './pages/portal/MyDocuments';
// import DocumentDetail from './pages/portal/DocumentDetail';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth fallback={<Landing />}>
            <AdminLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="convenios" element={<ConveniosList />} />
        <Route path="convenios/nuevo" element={<ConvenioForm />} />
        <Route path="convenios/:id" element={<ConvenioDetail />} />
        <Route path="convenios/:id/editar" element={<ConvenioForm />} />
        <Route path="inventario" element={<InventarioGeneral />} />
        <Route path="inventario/:convenioId" element={<InventarioConvenio />} />
        <Route path="afiliados" element={<AfiliadosList />} />
        <Route path="afiliados/:id" element={<AfiliadoDetail />} />
        <Route path="cupos" element={<CuposList />} />
        <Route path="transacciones" element={<TransaccionesList />} />
        <Route path="transacciones/:id" element={<TransaccionDetail />} />
        <Route path="reportes" element={<Reportes />} />
        <Route path="usuarios" element={<UsuariosList />} />
        <Route path="documentos-legales" element={<DocumentosLegales />} />
        <Route path="configuracion" element={<Configuracion />} />
        <Route path="*" element={<NotFound />} />
      </Route>

      {/* ===== Affiliate portal — fully separate experience, no admin nav ===== */}
      <Route path="/portal/login" element={<PortalLogin />} />
      <Route path="/portal/registro" element={<PortalRegister />} />
      <Route
        path="/portal"
        element={
          <RequireAffiliateAuth>
            <PortalLayout />
          </RequireAffiliateAuth>
        }
      >
        <Route index element={<PortalHome />} />
        <Route path="catalogo" element={<Catalogo />} />
        <Route path="catalogo/:id" element={<BenefitDetail />} />
        <Route path="cupo" element={<MiCupo />} />
        <Route path="perfil" element={<Profile />} />
        <Route path="perfil/editar" element={<EditProfile />} />
        <Route path="comprar/:id" element={<PurchaseFlow />} />
        <Route path="tickets" element={<MyTickets />} />
        <Route path="tickets/:id" element={<TicketDetail />} />
        <Route path="*" element={<PortalNotFound />} />
      </Route>
    </Routes>
  );
}
