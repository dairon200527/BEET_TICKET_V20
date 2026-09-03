import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States';
import { Badge } from '../../components/ui/Badge';
import { IconDocumentos } from '../../components/ui/Icons';
import * as documentosService from '../../services/documentosService';
import * as transaccionesService from '../../services/transaccionesService';
import * as convenioService from '../../services/convenioService';
import { formatCOP, formatDate, cuotasLabel } from '../../utils/format';

export default function MyDocuments() {
  const [documentos, setDocumentos] = useState([]);
  const [conveniosPorDoc, setConveniosPorDoc] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const cargar = () => {
    setLoading(true);
    setError(null);
    documentosService
      .misDocumentos({ pageSize: 100 })
      .then(async (data) => {
        setDocumentos(data.items);
        // DocumentoOut has no convenio reference directly — resolve it
        // through the document's own transaction (afiliado-scoped, so this
        // is always the affiliate's own data) and the active catalog.
        const catalogo = await convenioService.obtenerCatalogoAfiliado();
        const catalogoPorId = Object.fromEntries(catalogo.map((c) => [c.id, c]));
        const pares = await Promise.all(
          data.items.map((d) =>
            transaccionesService
              .miTransaccion(d.transaccion_id)
              .then((trx) => [d.id, catalogoPorId[trx.convenio_id] ?? null])
              .catch(() => [d.id, null])
          )
        );
        setConveniosPorDoc(Object.fromEntries(pares));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { cargar(); }, []);

  if (loading) return <LoadingState title="Cargando tus documentos…" />;
  if (error) return <ErrorState description={error} onRetry={cargar} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">Mis documentos</h1>
          <p className="page-subtitle">Documentos de asunción de deuda firmados al pagar con tu cupo de crédito.</p>
        </div>
      </div>

      {documentos.length === 0 ? (
        <EmptyState
          icon={<IconDocumentos color="var(--text-muted)" />}
          title="Aún no tienes documentos"
          description="Cuando compres un beneficio con tu cupo de crédito, el documento firmado aparecerá aquí."
        />
      ) : (
        <div className="portal-list-card">
          {documentos.map((d) => {
            const convenio = conveniosPorDoc[d.id];
            return (
              <Link key={d.id} to={`/portal/documentos/${d.id}`} className="portal-doc-row" style={{ textDecoration: 'none', color: 'inherit' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                  <span style={{ width: 36, height: 36, borderRadius: 8, background: 'var(--bg-brand-soft)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <IconDocumentos size={16} color="var(--brand-primary)" />
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>Asunción de deuda{convenio ? ` · ${convenio.nombre}` : ''}</div>
                    <div className="text-caption">{formatDate(d.fecha_firma)} · {formatCOP(d.valor)} · {cuotasLabel(d.numero_cuotas)}</div>
                  </div>
                </div>
                <Badge tone="green" dot>Firmado</Badge>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
