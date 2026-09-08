import { useNavigate } from 'react-router-dom';
import logo from '../assets/logo-beet-ticket.svg';
import Button from '../components/ui/Button';
import { useAuth } from '../context/AuthContext';

// Neutral entry point shown at "/" for anyone who isn't already signed in
// to the admin panel. It replaces the old behavior where the root route
// went straight into the Administrator flow (dashboard if authenticated,
// admin login if not) with no way to discover the Affiliate portal.
export default function Landing() {
  const navigate = useNavigate();
  const { nombreEntidad } = useAuth();

  return (
    <div className="login-page">
      <div className="login-card">
        <img src={logo} alt="BEET Ticket" height={72} style={{ marginBottom:38, alignItems: 'center' }} />
        <h1 className="text-h2" style={{ margin: '0 0 6px' }}>Bienvenido a BEET Ticket</h1>
        <p className="text-small" style={{ margin: '0 0 26px' }}>
          Elige cómo quieres ingresar a la plataforma de {nombreEntidad}.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Button size="lg" style={{ width: '100%' }} onClick={() => navigate('/login')}>
            Ingresar como administrador
          </Button>
          <Button size="lg" variant="secondary" style={{ width: '100%' }} onClick={() => navigate('/portal/login')}>
            Ingresar como afiliado
          </Button>
        </div>

        <div className="login-note text-caption">
          ¿Primera vez como afiliado? <a href="#" onClick={(e) => { e.preventDefault(); navigate('/portal/registro'); }} style={{ fontWeight: 600 }}>Activa tu cuenta</a>.
        </div>
      </div>
    </div>
  );
}
