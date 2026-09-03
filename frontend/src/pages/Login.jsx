import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import logo from '../assets/logo-beet-ticket.svg';
import Button from '../components/ui/Button';
import { Field, Input } from '../components/ui/Field';
import Alert from '../components/ui/Alert';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const { login, nombreEntidad } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [correo, setCorreo] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(correo, password);
      navigate('/');
    } catch (err) {
      // ApiError.message is always one of our own safe, user-facing
      // strings (see services/apiClient.js) — never a raw backend/SQL error.
      setError(err.message || 'No fue posible iniciar sesión. Intenta nuevamente.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <button
          onClick={() => navigate('/portal/login')}
          style={{ background: 'none', border: 'none', padding: 0, marginBottom: 16, cursor: 'pointer', color: 'var(--brand-primary)', fontWeight: 600, display: 'block' }}
        >
          ← Volver
        </button>
        <img src={logo} alt="BEET Ticket" height={52} style={{ marginBottom: 28 }} />
        <h1 className="text-h2" style={{ margin: '0 0 6px' }}>Panel administrativo</h1>
        <p className="text-small" style={{ margin: '0 0 26px' }}>Ingresa con tu cuenta de administrador de {nombreEntidad}.</p>

        {error && (
          <div style={{ marginBottom: 18 }}>
            <Alert tone="error" title="No se pudo iniciar sesión">{error}</Alert>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <Field label="Correo electrónico">
            <Input
              type="email"
              placeholder="nombre@cooperativaejemplo.com"
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              required
            />
          </Field>
          <Field label="Contraseña">
            <Input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
          <Button type="submit" size="lg" style={{ width: '100%', marginTop: 20 }} loading={loading}>
            Iniciar sesión
          </Button>
        </form>

        <div className="login-note text-caption">
          La autenticación se valida contra el backend real (FastAPI + PostgreSQL) en {import.meta.env.VITE_API_URL || 'http://localhost:8000'}.
        </div>
      </div>
    </div>
  );
}
