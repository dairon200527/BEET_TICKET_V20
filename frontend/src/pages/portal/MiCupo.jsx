import { Card, ProgressStatCard } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import { LoadingState } from '../../components/ui/States';
import { useMiCupo } from '../../hooks/useMiCupo';
import { formatCOP, percent } from '../../utils/format';

// Dedicated credit-quota screen — `GET /api/cupos/me` (see
// services/cuposService.js). `cupo_disponible` is the REAL, remaining
// balance stored directly on `cupos_credito` (not an accumulated "used"
// amount) — see ../../../SCHEMA_NOTES.md.
export default function MiCupo() {
  const { cupo, loading } = useMiCupo();

  if (loading) return <LoadingState title="Cargando tu cupo…" />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">Mi cupo de crédito</h1>
          <p className="page-subtitle">Saldo disponible para pagar beneficios con el cupo de tu cooperativa.</p>
        </div>
      </div>

      {cupo ? (
        <div className="grid grid-2 section-gap">
          <ProgressStatCard
            label="Cupo de crédito"
            pct={percent(cupo.cupo_total - cupo.cupo_disponible, cupo.cupo_total)}
            usedLabel={`Usado ${formatCOP(cupo.cupo_total - cupo.cupo_disponible)}`}
            availableLabel={`Disponible ${formatCOP(cupo.cupo_disponible)}`}
          />
          <Card>
            <div className="text-label" style={{ marginBottom: 12 }}>Detalle</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <Row label="Cupo total" value={formatCOP(cupo.cupo_total)} />
              <Row label="Cupo disponible" value={formatCOP(cupo.cupo_disponible)} />
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <span className="text-small">Estado</span>
                <StatusBadge status={cupo.estado} />
              </div>
            </div>
          </Card>
        </div>
      ) : (
        <Card>
          <div className="text-label" style={{ marginBottom: 10 }}>Sin cupo asignado</div>
          <div className="text-small cell-muted">Tu cooperativa aún no te ha asignado un cupo de crédito.</div>
        </Card>
      )}
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
