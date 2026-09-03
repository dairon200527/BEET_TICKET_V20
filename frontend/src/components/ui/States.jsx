import Button from './Button';
import { IconAlertas, IconInbox, IconLock, IconWarningTriangle } from './Icons';

export function SkeletonBlock({ lines = [{ w: '45%', h: 14 }, { w: '70%', h: 28 }, { w: '90%', h: 10 }, { w: '60%', h: 10 }] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {lines.map((l, i) => (
        <div key={i} className="skeleton-line" style={{ width: l.w, height: l.h }} />
      ))}
    </div>
  );
}

export function LoadingState({ title = 'Cargando…', description }) {
  return (
    <div className="state-card">
      <span className="state-icon" style={{ background: 'var(--bg-brand-soft)' }}>
        <span
          style={{
            width: 20,
            height: 20,
            border: '2.4px solid var(--brand-soft-border)',
            borderTopColor: 'var(--brand-primary)',
            borderRadius: 999,
            display: 'inline-block',
            animation: 'beetSpin 0.8s linear infinite',
          }}
        />
      </span>
      <div className="state-title">{title}</div>
      {description && <div className="state-desc">{description}</div>}
    </div>
  );
}

export function EmptyState({ icon, title, description, actionLabel, onAction }) {
  return (
    <div className="state-card">
      <span className="state-icon" style={{ background: 'var(--bg-app)', border: '1px solid var(--border-default)' }}>
        {icon ?? <IconInbox color="var(--text-muted)" />}
      </span>
      <div className="state-title">{title}</div>
      {description && <div className="state-desc">{description}</div>}
      {actionLabel && <Button size="sm" onClick={onAction}>{actionLabel}</Button>}
    </div>
  );
}

export function ErrorState({ title = 'No pudimos cargar la información', description = 'Error de conexión con el servidor. Código BT-503.', onRetry }) {
  return (
    <div className="state-card">
      <span className="state-icon" style={{ background: 'var(--error-soft)' }}>
        <IconWarningTriangle color="var(--error)" />
      </span>
      <div className="state-title">{title}</div>
      <div className="state-desc">{description}</div>
      <Button size="sm" variant="secondary" onClick={onRetry}>Reintentar</Button>
    </div>
  );
}

export function NoPermissionState({ nombreEntidad, role = 'Lector' }) {
  return (
    <div className="state-card">
      <span className="state-icon" style={{ background: 'var(--bg-app)', border: '1px solid var(--border-default)' }}>
        <IconLock color="var(--text-muted)" />
      </span>
      <div className="state-title">No tienes permisos para esta acción</div>
      <div className="state-desc">
        Tu rol es <strong style={{ fontWeight: 600 }}>{role}</strong>. Solicita acceso al súper administrador de {nombreEntidad}.
      </div>
    </div>
  );
}

export function AlertBanner({ title, description, icon }) {
  return (
    <div className="state-card" style={{ minHeight: 0 }}>
      <span className="state-icon" style={{ background: 'var(--warning-soft)' }}>
        {icon ?? <IconAlertas color="var(--warning)" />}
      </span>
      <div className="state-title">{title}</div>
      <div className="state-desc">{description}</div>
    </div>
  );
}
