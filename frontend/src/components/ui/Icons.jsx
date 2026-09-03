// Line icons at 1.6px stroke on a 20px grid, matching the BEET Ticket design
// system (section 05 — Iconografía). Kept as one module so every page pulls
// from the same visual language instead of ad-hoc SVGs.

const base = (size, color) => ({
  width: size,
  height: size,
  viewBox: '0 0 20 20',
  fill: 'none',
  stroke: color,
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
});

export function IconDashboard({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <rect x="2.5" y="2.5" width="6.5" height="6.5" rx="1.5" />
      <rect x="11" y="2.5" width="6.5" height="6.5" rx="1.5" />
      <rect x="2.5" y="11" width="6.5" height="6.5" rx="1.5" />
      <rect x="11" y="11" width="6.5" height="6.5" rx="1.5" />
    </svg>
  );
}
export function IconConvenios({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <rect x="2.5" y="4.5" width="15" height="11" rx="2" />
      <path d="M2.5 9h15M7 4.5v11" />
    </svg>
  );
}
export function IconInventario({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M2.5 6.5L10 2.5l7.5 4v7L10 17.5 2.5 13.5z" />
      <path d="M2.5 6.5L10 10.5l7.5-4M10 10.5v7" />
    </svg>
  );
}
export function IconAfiliados({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <circle cx="8" cy="7" r="3" />
      <path d="M2.5 16.5c0-2.8 2.5-4.5 5.5-4.5s5.5 1.7 5.5 4.5" />
      <path d="M14 5.5a3 3 0 010 5" />
    </svg>
  );
}
export function IconCupos({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <rect x="2.5" y="5" width="15" height="10" rx="2" />
      <path d="M2.5 8.5h15M5.5 12h4" />
    </svg>
  );
}
export function IconVentas({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M3 12.5l4-4 3 2.5 4.5-5" />
      <path d="M11.5 6h3v3" />
      <path d="M3 16.5h14" />
    </svg>
  );
}
export function IconRedencion({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <rect x="3" y="3" width="6" height="6" rx="1" />
      <rect x="11" y="3" width="6" height="6" rx="1" />
      <rect x="3" y="11" width="6" height="6" rx="1" />
      <path d="M11 11h2v2h-2zM15 15h2v2h-2z" />
    </svg>
  );
}
export function IconReportes({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M4.5 17V9M8.5 17V4M12.5 17v-6M16.5 17V7" />
    </svg>
  );
}
export function IconDocumentos({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <rect x="4" y="2.5" width="12" height="15" rx="2" />
      <path d="M7 6.5h6M7 10h6M7 13.5h3" />
    </svg>
  );
}
export function IconSeguridad({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M10 2.5l6 2.5v5c0 3.5-2.5 6-6 7.5-3.5-1.5-6-4-6-7.5V5z" />
      <path d="M7.5 10l1.8 1.8L13 8" />
    </svg>
  );
}
export function IconAhorro({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M10 2.5v15M14.5 6H8a2.5 2.5 0 000 5h3a2.5 2.5 0 010 5H5" />
    </svg>
  );
}
export function IconFirma({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M3 14c2-5 5-6.5 8-6.5M14.5 5.5L17 8l-2.5 2.5" />
      <path d="M3 17h14" />
    </svg>
  );
}
export function IconBuscar({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <circle cx="9" cy="9" r="6" />
      <path d="M13.5 13.5l4 4" />
    </svg>
  );
}
export function IconAlertas({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M10 3a4.5 4.5 0 00-4.5 4.5c0 4-1.5 5-1.5 5h12s-1.5-1-1.5-5A4.5 4.5 0 0010 3z" />
      <path d="M8.5 15.5a1.8 1.8 0 003 0" />
    </svg>
  );
}
export function IconDescargar({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M10 13V4M6.5 9.5L10 13l3.5-3.5" />
      <path d="M4 16h12" />
    </svg>
  );
}
export function IconConfiguracion({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <circle cx="10" cy="10" r="2.4" />
      <path d="M10 2.6v2.2M10 15.2v2.2M2.6 10h2.2M15.2 10h2.2M4.8 4.8l1.6 1.6M13.6 13.6l1.6 1.6M15.2 4.8l-1.6 1.6M6.4 13.6l-1.6 1.6" />
    </svg>
  );
}
export function IconPlus({ size = 16, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M10 4v12M4 10h12" />
    </svg>
  );
}
export function IconChevronDown({ size = 12, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M4 7l6 6 6-6" />
    </svg>
  );
}
export function IconUpload({ size = 24, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M10 14V4M6.5 7.5L10 4l3.5 3.5" />
      <path d="M4 16h12" />
    </svg>
  );
}
export function IconCheckCircle({ size = 20, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="8.5" stroke={color} strokeWidth="1.6" />
      <path d="M6.2 10.3l2.6 2.6 5-5.4" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
export function IconCheckSmall({ size = 12, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M2 6.3l2.2 2.2 5-5.4" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
export function IconInfoCircle({ size = 20, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="8.5" stroke={color} strokeWidth="1.6" />
      <path d="M10 9v5M10 6.2h0.01" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
export function IconWarningTriangle({ size = 20, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
      <path d="M10 3.2l7.3 13.6H2.7z" />
      <path d="M10 8v3.6M10 13.9h0.01" />
    </svg>
  );
}
export function IconWarningCircle({ size = 14, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="7" stroke={color} strokeWidth="1.5" />
      <path d="M8 4.6v4.2M8 11.2h0.01" stroke={color} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
export function IconClose({ size = 12, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M2.5 2.5l7 7M9.5 2.5l-7 7" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
export function IconClock({ size = 14, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
      <circle cx="8" cy="8" r="6.2" />
      <path d="M8 4.8V8l2.2 1.6" />
    </svg>
  );
}
export function IconTrendUp({ size = 14, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
      <path d="M8 12.5V4M4.5 7.5L8 4l3.5 3.5" />
    </svg>
  );
}
export function IconLock({ size = 20, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <rect x="4" y="9" width="12" height="8" rx="2" />
      <path d="M7 9V6.5a3 3 0 016 0V9" />
    </svg>
  );
}
export function IconInbox({ size = 20, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <rect x="2.5" y="5" width="15" height="11" rx="2" />
      <path d="M2.5 9h15" />
    </svg>
  );
}
export function IconGrid({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M3 5.5h14M6 10h8M8.5 14.5h3" />
    </svg>
  );
}
export function IconLogout({ size = 16, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M8 4H4.5A1.5 1.5 0 003 5.5v9A1.5 1.5 0 004.5 16H8" />
      <path d="M12.5 13.5L16 10l-3.5-3.5M16 10H7" />
    </svg>
  );
}
export function IconBell({ size = 18, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <path d="M10 3a4.5 4.5 0 00-4.5 4.5c0 4-1.5 5-1.5 5h12s-1.5-1-1.5-5A4.5 4.5 0 0010 3z" />
      <path d="M8.5 15.5a1.8 1.8 0 003 0" />
    </svg>
  );
}
export function IconQr({ size = 20, color = 'currentColor' }) {
  return (
    <svg {...base(size, color)}>
      <rect x="3" y="3" width="6" height="6" rx="1" />
      <rect x="11" y="3" width="6" height="6" rx="1" />
      <rect x="3" y="11" width="6" height="6" rx="1" />
      <path d="M11 11h2v2h-2zM15 15h2v2h-2z" />
    </svg>
  );
}
