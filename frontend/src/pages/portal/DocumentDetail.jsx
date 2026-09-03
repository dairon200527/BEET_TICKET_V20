import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { IconDocumentos } from '../../components/ui/Icons';
import Button from '../../components/ui/Button';
import * as documentosService from '../../services/documentosService';
import * as transaccionesService from '../../services/transaccionesService';
import * as convenioService from '../../services/convenioService';
import { useToast } from '../../context/ToastContext';
import { formatCOP, formatDateTime, cuotasLabel } from '../../utils/format';

export default function DocumentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();

  const [documento, setDocumento] = useState(undefined); // undefined = loading, null = not found/not yours
  const [convenio, setConvenio] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    documentosService
      .misDocumentos({ pageSize: 100 })
      .then(async (data) => {
        const found = data.items.find((d) => String(d.id) === id) ?? null;
        setDocumento(found);
        if (found) {
          const trx = await transaccionesService.miTransaccion(found.transaccion_id).catch(() => null);
          if (trx) {
            const catalogo = await convenioService.obtenerCatalogoAfiliado();
            setConvenio(catalogo.find((c) => c.id === trx.convenio_id) ?? null);
          }
        }
      })
      .catch((err) => setError(err.message));
  }, [id]);

  const descargar = async () => {
    try {
      const blob = await documentosService.descargarMiDocumento(documento.id);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      push({ title: 'No se pudo descargar el documento', description: err.message, variant: 'error' });
    }
  };

  if (error) return <ErrorState description={error} onRetry={() => window.location.reload()} />;
  if (documento === undefined) return <LoadingState title="Cargando documento…" />;
  if (!documento) {
    return <EmptyState title="Documento no encontrado" actionLabel="Volver a Mis documentos" onAction={() => navigate('/portal/documentos')} />;
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <button onClick={() => navigate('/portal/documentos')} className="text-small" style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--brand-primary)', fontWeight: 600 }}>
          ← Mis documentos
        </button>
      </div>

      <Card padding="card-pad-lg" style={{ maxWidth: 560 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <span style={{ width: 44, height: 44, borderRadius: 10, background: 'var(--bg-brand-soft)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
            <IconDocumentos size={20} color="var(--brand-primary)" />
          </span>
          <div>
            <h1 className="text-h3" style={{ margin: 0 }}>Asunción de deuda</h1>
            {convenio && <span className="text-caption">{convenio.nombre}</span>}
          </div>
          <span style={{ marginLeft: 'auto' }}><Badge tone="green" dot>Firmado</Badge></span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
          <Row label="Valor de la compra" value={formatCOP(documento.valor)} />
          <Row label="Cuotas autorizadas" value={cuotasLabel(documento.numero_cuotas)} />
          <Row label="Fecha de firma" value={formatDateTime(documento.fecha_firma)} />
        </div>

        <Button variant="secondary" onClick={descargar}>Descargar documento</Button>
      </Card>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
      <span className="text-small">{label}</span>
      <span style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );
}
