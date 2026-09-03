import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAffiliateAuth } from '../../context/AffiliateAuthContext';
import { Card, ProgressStatCard } from '../../components/ui/Card';
import { StatusBadge } from '../../components/ui/Badge';
import BenefitCard from '../../components/portal/BenefitCard';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States';
import * as convenioService from '../../services/convenioService';
import { useMiCupo } from '../../hooks/useMiCupo';
import { formatCOP, percent } from '../../utils/format';

export default function PortalHome() {
  const { afiliado } = useAffiliateAuth();
  const { cupo, loading: cupoLoading } = useMiCupo();

  const [catalogo, setCatalogo] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    convenioService
      .obtenerCatalogoAfiliado()
      .then(setCatalogo)
      .catch((err) => setError(err.message || 'No fue posible cargar la información.'))
      .finally(() => setLoading(false));
  }, []);

  const destacados = useMemo(() => catalogo.slice(0, 3), [catalogo]);

  return (
    <div>
      <div className="portal-hero">
        <h1 className="portal-hero-title">Hola, {afiliado.nombres} 👋</h1>
        <p className="portal-hero-sub">Consulta tu información, tu cupo de crédito y los beneficios disponibles para ti.</p>
      </div>

      <div className="grid grid-2 section-gap">
        <Card>
          <div className="text-label" style={{ marginBottom: 12 }}>Mi información</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <InfoRow label="Nombres" value={afiliado.nombres} />
            <InfoRow label="Apellidos" value={afiliado.apellidos} />
            <InfoRow label="Documento" value={afiliado.documento} />
            <InfoRow label="Cooperativa" value={afiliado.cooperativa_nombre} />
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span className="text-small">Estado</span>
              <StatusBadge status={afiliado.estado} />
            </div>
          </div>
          <Link to="/portal/perfil" style={{ display: 'inline-block', marginTop: 12, fontSize: 13, fontWeight: 600 }}>Ver mi perfil completo →</Link>
        </Card>

        {cupoLoading ? (
          <Card><LoadingState title="Cargando cupo…" /></Card>
        ) : cupo ? (
          <ProgressStatCard
            label="Cupo de crédito disponible"
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

      <div className="page-header">
        <div>
          <h2 className="text-h2" style={{ margin: 0 }}>Beneficios destacados</h2>
          <p className="page-subtitle">Precio BEET y ahorro, directamente de tu cooperativa.</p>
        </div>
        <Link to="/portal/catalogo" style={{ fontSize: 13, fontWeight: 600 }}>Ver todos los beneficios →</Link>
      </div>

      {loading ? (
        <div className="grid grid-3">
          {[0, 1, 2].map((i) => <Card key={i}><LoadingState title="Cargando…" /></Card>)}
        </div>
      ) : error ? (
        <ErrorState description={error} onRetry={() => window.location.reload()} />
      ) : destacados.length === 0 ? (
        <EmptyState title="No hay convenios disponibles actualmente" description="Muy pronto tu cooperativa habilitará nuevos beneficios." />
      ) : (
        <div className="grid grid-3">
          {destacados.map((c) => (
            <BenefitCard key={c.id} convenio={c} />
          ))}
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
      <span className="text-small">{label}</span>
      <span style={{ fontWeight: 500 }}>{value ?? '—'}</span>
    </div>
  );
}
