import { IconWarningCircle } from './Icons';

export function Field({ label, hint, error, optional, children }) {
  return (
    <label className="field">
      {label && (
        <span className="field-label">
          {label} {optional && <span className="field-optional">(opcional)</span>}
        </span>
      )}
      {children}
      {error ? (
        <span className="field-error">
          <IconWarningCircle size={14} color="var(--error)" />
          {error}
        </span>
      ) : hint ? (
        <span className="field-hint">{hint}</span>
      ) : null}
    </label>
  );
}

export function Input({ error, className = '', ...rest }) {
  return <input className={`input ${error ? 'has-error' : ''} ${className}`} {...rest} />;
}

export function Textarea({ error, className = '', rows = 4, ...rest }) {
  return <textarea rows={rows} className={`textarea ${error ? 'has-error' : ''} ${className}`} {...rest} />;
}

export function Select({ error, className = '', children, ...rest }) {
  return (
    <select className={`select ${error ? 'has-error' : ''} ${className}`} {...rest}>
      {children}
    </select>
  );
}

export function Checkbox({ label, className = '', ...rest }) {
  return (
    <label className={`checkbox-row ${className}`}>
      <input type="checkbox" {...rest} />
      <span className="checkbox-box">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M2.5 6.2l2.3 2.3 4.7-5" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </span>
      {label}
    </label>
  );
}

export function Radio({ label, className = '', ...rest }) {
  return (
    <label className={`radio-row ${className}`}>
      <input type="radio" {...rest} />
      <span className="radio-dot" />
      {label}
    </label>
  );
}

export function Switch({ label, className = '', ...rest }) {
  return (
    <label className={`switch-row ${className}`}>
      <input type="checkbox" {...rest} />
      <span className="switch-track">
        <span className="switch-thumb" />
      </span>
      {label}
    </label>
  );
}
