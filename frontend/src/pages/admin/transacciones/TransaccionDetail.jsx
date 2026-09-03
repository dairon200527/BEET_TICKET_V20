import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import { Card } from '../../../components/ui/Card';
import { StatusBadge } from '../../../components/ui/Badge';
import Avatar from '../../../components/ui/Avatar';
import Button from '../../../components/ui/Button';
import { EmptyState, ErrorState, LoadingState } from '../../../components/ui/States';
import Alert from '../../../components/ui/Alert';
import { IconFirma } from '../../../components/ui/Icons';
import * as transaccionesService from '../../../services/transaccionesService';
import * as afiliadosService from '../../../services/afiliadosService';
import * as convenioService from '../../../services/convenioService';
import * as documentosService from '../../../services/documentosService';
import { formatCOP, formatDateTime, cuotasLabel } from '../../../utils/format';

export default function TransaccionDetail() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [trx, setTrx] = useState(null);
  const [afiliado, setAfiliado] = useState(null);
  const [convenio, setConvenio] = useState(null);
  const [documento, setDocumento] = useState(null); // null = none for this transaction (real, not an error)
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useSetBreadcrumbs([
    { label: 'Transacciones', to: '/transacciones' },
    { label: id },
  ]);

  const cargar = useCallback(() => {
    setLoading(true);
    setError(null);
    transaccionesService
      .obtenerTransaccion(id)
      .then((t) => {
        setTrx(t);
        afiliadosService.obtenerAfiliado(t.afiliado_id).then(setAfiliado).catch(() => setAfiliado(null));
        convenioService.obtenerConvenio(t.convenio_id).then(setConvenio).catch(() => setConvenio(null));
        if (t.metodo_pago === 'CUPO') {
          documentosService
            .listarDocumentos({ pageSize: 100 })
            .then((data) => setDocumento(data.items.find((d) => d.transaccion_id === t.id) ?? null))
            .catch(() => setDocumento(null));
        }
      })
      .catch((err) => setError(err.status === 404 ? null : err.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { cargar(); }, [cargar]);

  if (loading) return <LoadingState title="Cargando transacción desde PostgreSQL…" />;
  if (error) return <ErrorState description={error} onRetry={cargar} />;
  if (!trx) {
    return <EmptyState title="Transacción no encontrada" actionLabel="Volver a transacciones" onAction={() => navigate('/transacciones')} />;
  }

  const nombreAfiliado = afiliado ? `${afiliado.nombres} ${afiliado.apellidos}` : '—';

  return (
    <div>
      <div className="page-header">
        <div>
          <span className="text-label text-mono">TRX-{trx.id}</span>
          <h1 className="text-h1 page-title">{convenio?.nombre ?? 'Convenio'}</h1>
          <p className="page-subtitle">{formatDateTime(trx.created_at)}</p>
        </div>
        <div className="page-header-actions">
          <StatusBadge status={trx.estado} />
        </div>
      </div>

      <div className="grid detail-grid-2col" style={{ '--col-ratio': '1.2fr 1fr', gap: 16 }}>
        <Card padding="card-pad-lg">
          <div className="text-label" style={{ marginBottom: 14 }}>Detalle de la compra</div>
          <div className="grid grid-3">
            <Detail label="Convenio" value={convenio?.nombre} />
            <Detail label="Unidades" value={trx.cantidad} />
            <Detail label="Subtotal" value={formatCOP(trx.subtotal)} />
            <Detail label="Total" value={formatCOP(trx.total)} />
            <Detail label="Forma de pago" value={trx.metodo_pago === 'TARJETA' ? 'Tarjeta débito/crédito' : 'Cupo de la cooperativa'} />
            {trx.metodo_pago === 'CUPO' && <Detail label="Cuotas" value={trx.numero_cuotas} />}
            {trx.referencia_pago && <Detail label="Referencia de pago" value={trx.referencia_pago} />}
            <Detail label="Fecha y hora" value={formatDateTime(trx.created_at)} />
          </div>

          {trx.codigos.length > 0 && (
            <div style={{ marginTop: 20, paddingTop: 20, borderTop: '1px solid var(--border-default)' }}>
              <div className="text-label" style={{ marginBottom: 10 }}>Unidades asignadas</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {trx.codigos.map((c) => (
                  <div key={c} style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--bg-app)', border: '1px solid var(--border-default)', borderRadius: 8, padding: '10px 12px' }}>
                    <span className="text-mono" style={{ flex: 1 }}>{c}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(trx.estado === 'RECHAZADA' || trx.estado === 'CANCELADA') && (
            <div style={{ marginTop: 20 }}>
              <Alert tone="error" title={trx.estado === 'RECHAZADA' ? 'La compra fue rechazada' : 'La compra fue cancelada'}>
                {trx.estado === 'RECHAZADA'
                  ? 'La transacción quedó registrada como rechazada — típicamente por saldo de cupo o inventario insuficiente al momento de la compra.'
                  : 'La transacción fue cancelada.'}
              </Alert>
            </div>
          )}
        </Card>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card padding="card-pad-lg">
            <div className="text-label" style={{ marginBottom: 12 }}>Afiliado</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <Avatar name={nombreAfiliado} />
              <div>
                <div style={{ fontWeight: 600 }}>{nombreAfiliado}</div>
                <div className="cell-muted text-mono">{afiliado?.documento}</div>
              </div>
            </div>
            {afiliado && (
              <Button size="sm" variant="ghost" style={{ marginTop: 12 }} onClick={() => navigate(`/afiliados/${afiliado.id}`)}>Ver perfil completo</Button>
            )}
          </Card>

          {documento && (
            <Card padding="card-pad-lg">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <span style={{ width: 36, height: 36, borderRadius: 8, background: 'var(--bg-brand-soft)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                  <IconFirma color="var(--brand-primary)" size={18} />
                </span>
                <div className="text-label" style={{ marginBottom: 0 }}>Documento de asunción de deuda</div>
              </div>
              <div style={{ marginBottom: 8 }}><StatusBadge status={documento.estado} /></div>
              <p className="text-small" style={{ marginTop: 0 }}>
                {documento.fecha_firma
                  ? `Firmado el ${formatDateTime(documento.fecha_firma)}.`
                  : `Generado el ${formatDateTime(documento.fecha_generacion)}, aún sin firmar.`}
                {' '}Autoriza {cuotasLabel(trx.numero_cuotas)} sobre el cupo de la cooperativa.
              </p>
              <p className="text-caption cell-muted" style={{ marginTop: 0 }}>
                La descarga del documento (Firebase Storage) no está conectada en esta integración.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <div className="text-label">{label}</div>
      <div style={{ fontSize: 14, fontWeight: 500 }} className="tabular">{value ?? '—'}</div>
    </div>
  );
}
