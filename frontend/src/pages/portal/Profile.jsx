import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAffiliateAuth } from '../../context/AffiliateAuthContext';
import { Card, ProgressStatCard } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import Avatar from '../../components/ui/Avatar';
import Button from '../../components/ui/Button';
import { ConfirmDialog } from '../../components/ui/Modal';
import { formatCOP, percent } from '../../utils/format';
import { useMiCupo } from '../../hooks/useMiCupo';

// Only correo/telefono are editable (PATCH /api/afiliados/me) — nombres,
// apellidos, documento, and estado stay under the cooperative's
// administration. Only fields the backend actually returns (AfiliadoOut:
// nombres, apellidos, documento, correo, telefono, estado,
// cooperativa_nombre) are shown — no ciudad/fecha_ingreso, which don't
// exist in the real schema.
export default function Profile() {
  const { afiliado, logout } = useAffiliateAuth();
  const { cupo, loading: cupoLoading } = useMiCupo();
  const navigate = useNavigate();
  const [confirmLogoutOpen, setConfirmLogoutOpen] = useState(false);

  const nombreCompleto = `${afiliado.nombres} ${afiliado.apellidos}`;

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <Avatar name={nombreCompleto} size="md" />
          <div>
            <h1 className="text-h1 page-title" style={{ marginTop: 0 }}>{nombreCompleto}</h1>
            <p className="page-subtitle text-mono">{afiliado.documento}</p>
          </div>
        </div>
        <div className="page-header-actions">
          <StatusBadge status={afiliado.estado} />
        </div>
      </div>

      <div className="grid grid-2 section-gap">
        <Card padding="card-pad-lg">
          <div className="text-label" style={{ marginBottom: 14 }}>Datos personales</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Row label="Nombres" value={afiliado.nombres} />
            <Row label="Apellidos" value={afiliado.apellidos} />
            <Row label="Documento" value={afiliado.documento} />
            <Row label="Correo electrónico" value={afiliado.correo} />
            <Row label="Teléfono" value={afiliado.telefono} />
            <Row label="Cooperativa" value={afiliado.cooperativa_nombre} />
          </div>
          <Button variant="secondary" style={{ marginTop: 16 }} onClick={() => navigate('/portal/perfil/editar')}>
            Editar datos de contacto
          </Button>
        </Card>

        {cupoLoading ? (
          <Card><div className="text-small cell-muted">Cargando cupo…</div></Card>
        ) : cupo ? (
          <ProgressStatCard
            label="Cupo de crédito"
            pct={percent(cupo.cupo_total - cupo.cupo_disponible, cupo.cupo_total)}
            usedLabel={`Usado ${formatCOP(cupo.cupo_total - cupo.cupo_disponible)}`}
            availableLabel={`Disponible ${formatCOP(cupo.cupo_disponible)}`}
          />
        ) : (
          <Card>
            <div className="text-label" style={{ marginBottom: 10 }}>Cupo de crédito</div>
            <div className="text-small cell-muted">Tu cooperativa aún no te ha asignado un cupo de crédito.</div>
          </Card>
        )}
      </div>

      <Button variant="danger" onClick={() => setConfirmLogoutOpen(true)}>Cerrar sesión</Button>

      <ConfirmDialog
        open={confirmLogoutOpen}
        onClose={() => setConfirmLogoutOpen(false)}
        onConfirm={() => { logout(); navigate('/portal/login'); }}
        title="¿Cerrar sesión?"
        description="Vas a salir del portal del afiliado. Tendrás que volver a iniciar sesión para continuar."
        confirmLabel="Cerrar sesión"
      />
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
      <span className="text-small">{label}</span>
      <span style={{ fontWeight: 500 }}>{value ?? '—'}</span>
    </div>
  );
}
