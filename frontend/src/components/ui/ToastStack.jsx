import { IconCheckCircle, IconInfoCircle } from './Icons';

export default function ToastStack({ toasts, onDismiss }) {
  if (!toasts.length) return null;
  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <div className="toast" key={t.id}>
          {t.variant === 'error' ? (
            <IconInfoCircle size={18} color="var(--dark-error-icon)" />
          ) : (
            <IconCheckCircle size={18} color="var(--accent-green)" />
          )}
          <div style={{ flex: 1 }}>
            <div className="toast-title">{t.title}</div>
            {t.description && <div className="toast-body">{t.description}</div>}
          </div>
          {t.actionLabel ? (
            <button className="toast-action" onClick={() => { t.onAction?.(); onDismiss(t.id); }}>{t.actionLabel}</button>
          ) : (
            <button className="toast-close" onClick={() => onDismiss(t.id)} aria-label="Cerrar">×</button>
          )}
        </div>
      ))}
    </div>
  );
}
