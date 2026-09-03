import { IconCheckCircle, IconInfoCircle, IconWarningTriangle } from './Icons';

const CONFIG = {
  success: { cls: 'alert-success', icon: <IconCheckCircle color="var(--success-text)" /> },
  info: { cls: 'alert-info', icon: <IconInfoCircle color="var(--brand-primary)" /> },
  warning: { cls: 'alert-warning', icon: <IconWarningTriangle color="var(--warning)" /> },
  error: { cls: 'alert-error', icon: <IconInfoCircle color="var(--error)" /> },
};

export default function Alert({ tone = 'info', title, children }) {
  const cfg = CONFIG[tone];
  return (
    <div className={`alert ${cfg.cls}`}>
      <span className="alert-icon">{cfg.icon}</span>
      <div>
        {title && <div className="alert-title">{title}</div>}
        <div className="alert-body">{children}</div>
      </div>
    </div>
  );
}
