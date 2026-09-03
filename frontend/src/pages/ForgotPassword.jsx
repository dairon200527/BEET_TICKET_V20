import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import logo from '../assets/logo-beet-ticket.svg';
import Button from '../components/ui/Button';
import { Field, Input } from '../components/ui/Field';
import Alert from '../components/ui/Alert';
import * as authService from '../services/authService';

// Shared "forgot password" flow for both the Administrator and Affiliate
// login screens (variant changes copy + which real endpoint it calls).
// The backend always returns the same generic message whether or not the
// identifier exists — that's what actually prevents account enumeration,
// see backend/README.md. No real email provider is wired up yet, so in
// development the backend's response embeds the reset token directly
// ("dev-only-token:...") purely so this flow is testable end-to-end
// without one; in production that prefix never appears and the user is
// simply told to check their email.
const COPY = {
  admin: {
    subtitle: 'Panel administrativo',
    identifierLabel: 'Correo electrónico',
    identifierPlaceholder: 'nombre@cooperativaejemplo.com',
    loginPath: '/login',
    loginLabel: 'Volver a iniciar sesión',
    forgot: authService.adminForgotPassword,
    reset: authService.adminResetPassword,
  },
  affiliate: {
    subtitle: 'Portal del afiliado',
    identifierLabel: 'Correo electrónico o cédula',
    identifierPlaceholder: 'Ej. nombre@correo.com o 52114908',
    loginPath: '/portal/login',
    loginLabel: 'Volver a iniciar sesión',
    forgot: authService.afiliadoForgotPassword,
    reset: authService.afiliadoResetPassword,
  },
};

const DEV_TOKEN_PREFIX = 'dev-only-token:';

export default function ForgotPassword({ variant = 'admin' }) {
  const copy = COPY[variant] ?? COPY.admin;
  const navigate = useNavigate();

  const [step, setStep] = useState('identificar'); // identificar | restablecer | pendiente-correo | exito
  const [identifier, setIdentifier] = useState('');
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const handleIdentify = async (e) => {
    e.preventDefault();
    if (!identifier.trim()) {
      setErrors({ identifier: 'Este campo es obligatorio.' });
      return;
    }
    setErrors({});
    setLoading(true);
    try {
      const { detail } = await copy.forgot(identifier.trim());
      if (detail?.startsWith(DEV_TOKEN_PREFIX)) {
        setToken(detail.slice(DEV_TOKEN_PREFIX.length));
        setStep('restablecer');
      } else {
        setStep('pendiente-correo');
      }
    } catch {
      // The backend never fails this call in a way that reveals whether
      // the identifier exists — a network/500 is the only real failure mode.
      setErrors({ identifier: 'No pudimos procesar la solicitud. Intenta de nuevo en unos minutos.' });
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    const nextErrors = {};
    if (password.length < 6) nextErrors.password = 'La contraseña debe tener al menos 6 caracteres.';
    if (password !== confirm) nextErrors.confirm = 'Las contraseñas no coinciden.';
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    setLoading(true);
    try {
      await copy.reset(token, password, confirm);
      setStep('exito');
    } catch (err) {
      setErrors({ password: err.message || 'El enlace de recuperación es inválido o expiró.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <img src={logo} alt="BEET Ticket" height={52} style={{ marginBottom: 28 }} />

        {step === 'identificar' && (
          <>
            <h1 className="text-h2" style={{ margin: '0 0 6px' }}>Recuperar contraseña</h1>
            <p className="text-small" style={{ margin: '0 0 26px' }}>{copy.subtitle} · confirma tu identidad para continuar.</p>
            <form onSubmit={handleIdentify}>
              <Field label={copy.identifierLabel} error={errors.identifier}>
                <Input
                  type="text"
                  placeholder={copy.identifierPlaceholder}
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                />
              </Field>
              <Button type="submit" size="lg" style={{ width: '100%' }} loading={loading}>
                Continuar
              </Button>
            </form>
          </>
        )}

        {step === 'pendiente-correo' && (
          <>
            <Alert tone="success" title="Revisa tu correo">
              Si la cuenta existe, te enviamos instrucciones para restablecer tu contraseña.
            </Alert>
            <Button size="lg" style={{ width: '100%', marginTop: 20 }} onClick={() => navigate(copy.loginPath)}>
              Volver a iniciar sesión
            </Button>
          </>
        )}

        {step === 'restablecer' && (
          <>
            <h1 className="text-h2" style={{ margin: '0 0 6px' }}>Crea una nueva contraseña</h1>
            <p className="text-small" style={{ margin: '0 0 26px' }}>Define y confirma tu nueva contraseña.</p>
            <form onSubmit={handleReset}>
              <Field label="Nueva contraseña" error={errors.password}>
                <Input
                  type="password"
                  placeholder="Mínimo 6 caracteres"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>
              <Field label="Confirmar nueva contraseña" error={errors.confirm}>
                <Input
                  type="password"
                  placeholder="Repite tu nueva contraseña"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </Field>
              <Button type="submit" size="lg" style={{ width: '100%' }} loading={loading}>
                Restablecer contraseña
              </Button>
            </form>
          </>
        )}

        {step === 'exito' && (
          <>
            <Alert tone="success" title="Contraseña actualizada">
              Tu contraseña se restableció correctamente. Ya puedes iniciar sesión con tu nueva contraseña.
            </Alert>
            <Button size="lg" style={{ width: '100%', marginTop: 20 }} onClick={() => navigate(copy.loginPath)}>
              Ir a iniciar sesión
            </Button>
          </>
        )}

        {step !== 'exito' && step !== 'pendiente-correo' && (
          <div className="login-note text-caption">
            <Link to={copy.loginPath} style={{ fontWeight: 600 }}>{copy.loginLabel}</Link>.
          </div>
        )}
      </div>
    </div>
  );
}
