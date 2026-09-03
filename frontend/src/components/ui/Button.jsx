const VARIANT_CLASS = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  soft: 'btn-soft',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
  'danger-solid': 'btn-danger-solid',
};

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon = null,
  disabled = false,
  className = '',
  children,
  ...rest
}) {
  return (
    <button
      type="button"
      className={`btn ${VARIANT_CLASS[variant]} btn-${size} ${className}`}
      disabled={disabled || loading}
      style={loading ? { cursor: 'progress', opacity: 0.9 } : undefined}
      {...rest}
    >
      {loading ? <span className="btn-spinner" /> : icon}
      {children}
    </button>
  );
}

export function IconButton({ icon, size = 'md', label, className = '', ...rest }) {
  return (
    <button type="button" className={`btn-icon ${size === 'sm' ? 'btn-icon-sm' : ''} ${className}`} aria-label={label} {...rest}>
      {icon}
    </button>
  );
}
