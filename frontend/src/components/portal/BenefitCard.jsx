import { Link } from 'react-router-dom';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import ConvenioImagenMarca from './ConvenioImagenMarca';
import { formatCOP, formatDate } from '../../utils/format';

// `convenio` here is the real ConvenioOut shape (see
// backend/app/schemas/convenio.py) — no `marca`/`categoria`/`tope` fields,
// those don't exist in the real `convenios` table (see ../../../../SCHEMA_NOTES.md).
export default function BenefitCard({ convenio }) {
  const ahorro = convenio.precio_publico - convenio.precio_beet;
  const ahorroPct = Math.round((ahorro / convenio.precio_publico) * 100);

  return (
    <Link to={`/portal/catalogo/${convenio.id}`} className="benefit-card-link">
      <Card padding="" className="benefit-card">
        <ConvenioImagenMarca imagenMarcaUrl={convenio.imagen_marca_url} nombre={convenio.nombre} />
        <div className="benefit-card-body">
          <div className="benefit-card-top">
            <div style={{ fontSize: 15, fontWeight: 600 }}>{convenio.nombre}</div>
            <Badge tone="green" dot>Ahorras {ahorroPct}%</Badge>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 10 }}>
            <span className="tabular" style={{ fontSize: 20, fontWeight: 600 }}>{formatCOP(convenio.precio_beet)}</span>
            <span className="tabular text-small" style={{ textDecoration: 'line-through' }}>{formatCOP(convenio.precio_publico)}</span>
          </div>
          <div className="text-caption" style={{ marginTop: 8 }}>
            {convenio.fecha_fin ? `Vigente hasta ${formatDate(convenio.fecha_fin)}` : 'Sin fecha de vencimiento'}
          </div>
        </div>
      </Card>
    </Link>
  );
}
