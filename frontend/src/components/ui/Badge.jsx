import { IconCheckSmall, IconClose, IconWarningTriangle } from './Icons';

export function Badge({ tone = 'neutral', dot = false, icon = null, children }) {
  return (
    <span className={`badge badge-${tone}`}>
      {dot && <span className="badge-dot" />}
      {icon}
      {children}
    </span>
  );
}

// Maps the five inventory states + transaction/affiliate states from the
// functional spec to a fixed badge, so the same status always looks the same
// everywhere in the app.
const STATUS_MAP = {
  // Inventario
  Disponible: { tone: 'green', dot: true },
  Reservado: { tone: 'blue', dot: true },
  Entregado: { tone: 'blue-solid', icon: <IconCheckSmall color="var(--brand-primary)" /> },
  Utilizado: { tone: 'neutral', dot: true },
  'Próximo a vencer': { tone: 'amber', icon: <IconWarningTriangle size={12} color="var(--warning)" /> },
  Cancelado: { tone: 'red', icon: <IconClose color="var(--error)" /> },
  Vencido: { tone: 'vencido' },
  // Transacciones
  Procesando: { tone: 'blue', spinner: true },
  Rechazado: { tone: 'red', icon: <IconClose color="var(--error)" /> },
  // Afiliados / cupos
  activo: { tone: 'green', dot: true, label: 'Activo' },
  retirado: { tone: 'neutral', dot: true, label: 'Retirado' },
  suspendido: { tone: 'amber', label: 'Suspendido' },
  inactivo: { tone: 'neutral', dot: true, label: 'Inactivo' },
  // Real backend inventory states (app/models/enums.py::EstadoUnidadInventario)
  // — lowercase, distinct from the capitalized mock labels above.
  disponible: { tone: 'green', dot: true, label: 'Disponible' },
  bloqueada: { tone: 'amber', label: 'Bloqueada' },
  entregada: { tone: 'blue-solid', icon: <IconCheckSmall color="var(--brand-primary)" />, label: 'Entregada' },
  redimida: { tone: 'neutral', dot: true, label: 'Redimida' },
  cancelada: { tone: 'red', icon: <IconClose color="var(--error)" />, label: 'Cancelada' },
  vencida: { tone: 'vencido', label: 'Vencida' },
  // Real backend transaction states (app/models/enums.py::EstadoTransaccion)
  // — uppercase, matching the real database's CHECK constraint exactly.
  // Includes CANCELADA at the transaction level (in addition to unit-level
  // cancellation), unlike an earlier design assumption.
  PENDIENTE: { tone: 'blue', spinner: true, label: 'Pendiente' },
  APROBADA: { tone: 'blue-solid', icon: <IconCheckSmall color="var(--brand-primary)" />, label: 'Aprobada' },
  RECHAZADA: { tone: 'red', icon: <IconClose color="var(--error)" />, label: 'Rechazada' },
  CANCELADA: { tone: 'red', icon: <IconClose color="var(--error)" />, label: 'Cancelada' },
  COMPLETADA: { tone: 'blue-solid', icon: <IconCheckSmall color="var(--brand-primary)" />, label: 'Completada' },
  // documentos_asuncion_deuda.estado
  FIRMADO: { tone: 'green', dot: true, label: 'Firmado' },
  CANCELADO: { tone: 'red', icon: <IconClose color="var(--error)" />, label: 'Cancelado' },
};

export function StatusBadge({ status }) {
  // usuarios_admin/afiliados/convenios/cupos_credito/plantillas.estado are
  // plain PostgreSQL booleans in the real schema (not a string enum) — map
  // true/false to the existing activo/inactivo badge look.
  if (typeof status === 'boolean') status = status ? 'activo' : 'inactivo';
  const cfg = STATUS_MAP[status] ?? { tone: 'neutral' };
  const toneClass = cfg.tone === 'blue-solid' ? 'blue-solid' : cfg.tone;
  return (
    <span className={`badge badge-${toneClass}`}>
      {cfg.dot && <span className="badge-dot" />}
      {cfg.spinner && (
        <span
          style={{
            width: 9,
            height: 9,
            border: '1.8px solid var(--brand-primary)',
            borderTopColor: 'transparent',
            borderRadius: 999,
            display: 'inline-block',
            animation: 'beetSpin 0.8s linear infinite',
          }}
        />
      )}
      {cfg.icon}
      {cfg.label ?? status}
    </span>
  );
}

export function RoleBadge({ role }) {
  if (role === 'Súper administrador') return <Badge tone="brand-solid">Súper admin</Badge>;
  if (role === 'Administrador') return <Badge tone="blue">Administrador</Badge>;
  return <Badge tone="outline">Lector</Badge>;
}
