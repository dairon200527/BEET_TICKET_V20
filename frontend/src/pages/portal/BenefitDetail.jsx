import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import ConvenioImagenMarca from '../../components/portal/ConvenioImagenMarca';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States';
import * as convenioService from '../../services/convenioService';
import { formatCOP, formatDate } from '../../utils/format';

// There is no per-id affiliate-facing convenio endpoint — only the catalog
// list (GET /api/convenios/catalogo). Fetching that list and finding the
// one that matches is the real equivalent.
export default function BenefitDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [convenio, setConvenio] = useState(undefined); // undefined = loading, null = not found
  const [error, setError] = useState(null);

  useEffect(() => {
    convenioService
      .obtenerCatalogoAfiliado()
      .then((data) => setConvenio(data.find((c) => c.id === Number(id)) ?? null))
      .catch((err) => setError(err.message || 'No fue posible cargar la información.'));
  }, [id]);

  if (error) return <ErrorState description={error} onRetry={() => window.location.reload()} />;
  if (convenio === undefined) return <LoadingState title="Cargando beneficio…" />;
  if (!convenio) {
    return <EmptyState title="Beneficio no encontrado" description="Puede que ya no esté disponible en el catálogo." actionLabel="Volver al catálogo" onAction={() => navigate('/portal/catalogo')} />;
  }

  const ahorro = convenio.precio_publico - convenio.precio_beet;
  const ahorroPct = Math.round((ahorro / convenio.precio_publico) * 100);

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <button onClick={() => navigate('/portal/catalogo')} className="text-small" style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--brand-primary)', fontWeight: 600 }}>
          ← Volver al catálogo
        </button>
      </div>

      <div className="grid detail-grid-2col" style={{ '--col-ratio': '1.1fr 1fr', gap: 20, alignItems: 'start' }}>
        <Card padding="" style={{ overflow: 'hidden' }}>
          <ConvenioImagenMarca imagenMarcaUrl={convenio.imagen_marca_url} nombre={convenio.nombre} style={{ height: 220 }} />
        </Card>

        <div>
          <h1 className="text-h1" style={{ margin: '0 0 10px' }}>{convenio.nombre}</h1>

          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 12, marginBottom: 8 }}>
            <span className="text-display tabular">{formatCOP(convenio.precio_beet)}</span>
            <span className="text-small" style={{ textDecoration: 'line-through' }}>{formatCOP(convenio.precio_publico)}</span>
            <Badge tone="green" dot>Ahorras {formatCOP(ahorro)} ({ahorroPct}%)</Badge>
          </div>

          <p className="text-body" style={{ color: 'var(--text-muted)' }}>{convenio.descripcion || 'Sin descripción adicional registrada.'}</p>

          <div className="grid grid-2" style={{ margin: '18px 0' }}>
            <div>
              <div className="text-label">Inicio de vigencia</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{formatDate(convenio.fecha_inicio)}</div>
            </div>
            <div>
              <div className="text-label">Fin de vigencia</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>{convenio.fecha_fin ? formatDate(convenio.fecha_fin) : 'Sin fecha de vencimiento'}</div>
            </div>
          </div>

          <Button style={{ width: '100%' }} onClick={() => navigate(`/portal/comprar/${convenio.id}`)}>
            Comprar este beneficio
          </Button>
        </div>
      </div>
    </div>
  );
}
