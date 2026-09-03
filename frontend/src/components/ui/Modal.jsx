import { useEffect } from 'react';
import Button from './Button';
import { IconWarningTriangle } from './Icons';

export default function Modal({ open, onClose, title, children, size = 'md', actions }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className={`modal-panel ${size === 'lg' ? 'modal-lg' : ''}`} role="dialog" aria-modal="true">
        {title && <h3 className="modal-title">{title}</h3>}
        <div className="modal-body" style={{ color: 'var(--text-primary)' }}>{children}</div>
        {actions && <div className="modal-actions">{actions}</div>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, onClose, onConfirm, title, description, confirmLabel = 'Confirmar', tone = 'danger', loading = false }) {
  if (!open) return null;
  return (
    <div className="modal-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-panel" role="alertdialog" aria-modal="true">
        <span className="modal-icon" style={{ background: tone === 'danger' ? 'var(--error-soft)' : 'var(--bg-brand-soft)' }}>
          <IconWarningTriangle color={tone === 'danger' ? 'var(--error)' : 'var(--brand-primary)'} />
        </span>
        <h3 className="modal-title">{title}</h3>
        <p className="modal-body">{description}</p>
        <div className="modal-actions">
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button variant={tone === 'danger' ? 'danger-solid' : 'primary'} onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  );
}
