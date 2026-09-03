import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Stepper from '../../components/ui/Stepper';
import { Card } from '../../components/ui/Card';
import Button, { IconButton } from '../../components/ui/Button';
import { Radio, Select, Field, Input } from '../../components/ui/Field';
import Alert from '../../components/ui/Alert';
import { LoadingState, EmptyState, ErrorState } from '../../components/ui/States';
import SignaturePad from '../../components/ui/SignaturePad';
import * as convenioService from '../../services/convenioService';
import * as transaccionesService from '../../services/transaccionesService';
import { useMiCupo } from '../../hooks/useMiCupo';
import { useToast } from '../../context/ToastContext';
import { formatCOP, cuotasLabel, percent } from '../../utils/format';

const CUOTAS_OPCIONES = [1, 3, 6, 12];

export default function PurchaseFlow() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();
  const { cupo, loading: cupoLoading, refrescar: refrescarCupo } = useMiCupo();

  const [convenio, setConvenio] = useState(undefined);
  const [loadError, setLoadError] = useState(null);

  const [step, setStep] = useState('cantidad');
  const [cantidad, setCantidad] = useState(1);
  const [metodoPago, setMetodoPago] = useState('tarjeta');
  const [cuotas, setCuotas] = useState(3);
  const [numeroTarjeta, setNumeroTarjeta] = useState('');
  const [firmaBase64, setFirmaBase64] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [compraError, setCompraError] = useState('');
  const [compraErrorTipo, setCompraErrorTipo] = useState(null); // 'rechazado_fondos' | 'rechazado_invalida' | 'error_pasarela' | null

  useEffect(() => {
    convenioService
      .obtenerCatalogoAfiliado()
      .then((data) => setConvenio(data.find((c) => c.id === Number(id)) ?? null))
      .catch((err) => setLoadError(err.message));
  }, [id]);

  const cupoDisponible = cupo ? cupo.cupo_disponible : 0;
  // No affiliate-facing stock-count endpoint exists — the real inventory
  // check happens server-side, atomically, at the moment of purchase (see
  // backend/app/services/transaction_service.py). The real schema also has
  // no per-convenio purchase-cap column (`convenios` has no `tope`), so
  // this is a UI-only sane default, not a value read from the backend.
  const maxUnidades = convenio ? 10 : 0;
  const total = convenio ? convenio.precio_beet * cantidad : 0;
  const cupoInsuficiente = metodoPago === 'cupo' && !!cupo && total > cupoDisponible;

  const steps = useMemo(() => {
    const base = [
      { key: 'cantidad', label: 'Cantidad' },
      { key: 'pago', label: 'Pago' },
      { key: 'resumen', label: 'Checkout' },
    ];
    if (metodoPago === 'cupo') base.push({ key: 'firma', label: 'Firma' });
    base.push({ key: 'resultado', label: 'Ticket' });
    return base;
  }, [metodoPago]);

  if (loadError) return <ErrorState description={loadError} onRetry={() => window.location.reload()} />;
  if (convenio === undefined || cupoLoading) return <LoadingState title="Cargando…" />;
  if (!convenio) {
    return <EmptyState title="Beneficio no encontrado" actionLabel="Volver al catálogo" onAction={() => navigate('/portal/catalogo')} />;
  }

  const ejecutarCompra = async (firma) => {
    setCompraError('');
    setCompraErrorTipo(null);
    try {
      const trx = await transaccionesService.comprar({
        convenio_id: convenio.id,
        cantidad,
        metodo_pago: metodoPago,
        numero_cuotas: metodoPago === 'cupo' ? cuotas : undefined,
        firma_base64: metodoPago === 'cupo' ? firma : undefined,
        numero_tarjeta: metodoPago === 'tarjeta' ? numeroTarjeta : undefined,
      });
      // A rejected/errored card payment is a successful API call (201)
      // carrying estado=RECHAZADA — the mock gateway's decline is a real
      // business outcome, not an HTTP error — so it must be told apart
      // here from an actually completed purchase. `resultado_pago`
      // distinguishes the 3 non-approved outcomes so the message (and
      // whether "reintentar" makes sense) matches what actually happened.
      if (trx.estado === 'RECHAZADA') {
        setCompraError(trx.motivo_rechazo || 'Tu banco rechazó el pago.');
        setCompraErrorTipo(trx.resultado_pago || 'rechazado_fondos');
        setStep('resumen');
        return;
      }
      setResultado(trx);
      setStep('resultado');
      if (metodoPago === 'cupo') {
        push({ title: 'Firma registrada', description: `Autorizaste ${cuotasLabel(cuotas)} sobre tu cupo de crédito.` });
        // The header's cupo chip (and "Mi cupo") hold their own copy of
        // this value, fetched once when the portal session started —
        // without this, they'd keep showing the pre-purchase balance
        // until a full page reload (see AffiliateAuthContext.jsx).
        refrescarCupo();
      }
    } catch (err) {
      setCompraError(err.message || 'No fue posible completar la compra.');
      setCompraErrorTipo(null);
      setStep(metodoPago === 'cupo' ? 'firma' : 'resumen');
    }
  };

  const confirmarCompra = () => {
    if (metodoPago === 'cupo') {
      setStep('firma');
    } else {
      setStep('confirmando');
      ejecutarCompra(null);
    }
  };

  const firmarYConfirmar = () => {
    setStep('confirmando');
    ejecutarCompra(firmaBase64);
  };

  return (
    <div>
      <div style={{ marginBottom: 6 }}>
        <h1 className="text-h2" style={{ margin: '2px 0 18px' }}>{convenio.nombre}</h1>
      </div>

      {step !== 'confirmando' && step !== 'resultado' && <Stepper steps={steps} currentKey={step} />}

      {step === 'cantidad' && (
        <Card padding="card-pad-lg">
          <div className="text-label" style={{ marginBottom: 14 }}>¿Cuántas unidades quieres comprar?</div>
          {maxUnidades < 1 ? (
            <EmptyState title="Este beneficio no admite compras" description="Consulta con tu cooperativa." actionLabel="Volver al catálogo" onAction={() => navigate('/portal/catalogo')} />
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <IconButton label="Menos" onClick={() => setCantidad((c) => Math.max(1, c - 1))} icon={<span style={{ fontSize: 18, lineHeight: 1 }}>−</span>} />
                <span className="text-display tabular" style={{ minWidth: 48, textAlign: 'center' }}>{cantidad}</span>
                <IconButton label="Más" onClick={() => setCantidad((c) => Math.min(maxUnidades, c + 1))} icon={<span style={{ fontSize: 18, lineHeight: 1 }}>+</span>} />
                <span className="text-caption">máximo {maxUnidades} por esta compra</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', margin: '20px 0', paddingTop: 16, borderTop: '1px solid var(--border-default)' }}>
                <span className="text-small">Precio unitario</span>
                <span className="tabular" style={{ fontWeight: 500 }}>{formatCOP(convenio.precio_beet)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
                <span style={{ fontWeight: 600 }}>Subtotal</span>
                <span className="tabular" style={{ fontWeight: 600, fontSize: 18 }}>{formatCOP(total)}</span>
              </div>
              <Button style={{ width: '100%' }} onClick={() => setStep('pago')}>Continuar</Button>
            </>
          )}
        </Card>
      )}

      {step === 'pago' && (
        <Card padding="card-pad-lg">
          <div className="text-label" style={{ marginBottom: 14 }}>Forma de pago</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 20 }}>
            <Radio name="pago" label="Tarjeta débito o crédito" checked={metodoPago === 'tarjeta'} onChange={() => setMetodoPago('tarjeta')} />
            <Radio name="pago" label="Cupo de crédito de la cooperativa" checked={metodoPago === 'cupo'} disabled={!cupo} onChange={() => setMetodoPago('cupo')} />
            {!cupo && <div className="text-caption" style={{ marginLeft: 26 }}>No tienes un cupo de crédito asignado.</div>}
          </div>

          {metodoPago === 'tarjeta' && (
            <div style={{ marginBottom: 20 }}>
              <Field label="Número de tarjeta">
                <Input
                  inputMode="numeric"
                  placeholder="4111 1111 1111 0000"
                  value={numeroTarjeta}
                  onChange={(e) => setNumeroTarjeta(e.target.value.replace(/[^0-9]/g, ''))}
                  maxLength={19}
                />
              </Field>
              {import.meta.env.DEV && (
                <div className="text-caption" style={{ marginTop: 10, background: 'var(--bg-app)', border: '1px solid var(--border-default)', borderRadius: 8, padding: 10 }}>
                  <strong>Solo en desarrollo · tarjetas de prueba (sandbox, sin pasarela real):</strong>
                  <div>Termina en 0000 → aprobada</div>
                  <div>Termina en 0001 → rechazada (fondos insuficientes)</div>
                  <div>Termina en 0002 → rechazada (tarjeta inválida/vencida)</div>
                  <div>Termina en 0003 → error de la pasarela (timeout)</div>
                  <div>Cualquier otro número → aprobada por defecto</div>
                </div>
              )}
            </div>
          )}

          {metodoPago === 'cupo' && cupo && (
            <div style={{ marginBottom: 20 }}>
              <div className="progress-track" style={{ marginBottom: 8 }}>
                <div className="progress-fill green" style={{ width: `${percent(cupo.cupo_total - cupo.cupo_disponible, cupo.cupo_total)}%` }} />
              </div>
              <div className="text-caption" style={{ marginBottom: 16 }}>Cupo disponible: {formatCOP(cupoDisponible)}</div>

              <label className="field-label" style={{ display: 'block', marginBottom: 6 }}>Número de cuotas</label>
              <Select value={cuotas} onChange={(e) => setCuotas(Number(e.target.value))} style={{ marginBottom: 12 }}>
                {CUOTAS_OPCIONES.map((n) => <option key={n} value={n}>{cuotasLabel(n)}</option>)}
              </Select>

              {cupoInsuficiente && (
                <Alert tone="error" title="Saldo de cupo insuficiente">
                  El saldo disponible ({formatCOP(cupoDisponible)}) es menor al valor de la compra ({formatCOP(total)}). Elige otra forma de pago o reduce la cantidad.
                </Alert>
              )}
            </div>
          )}

          <div style={{ display: 'flex', gap: 10 }}>
            <Button variant="secondary" onClick={() => setStep('cantidad')}>Atrás</Button>
            <Button style={{ flex: 1 }} disabled={cupoInsuficiente || (metodoPago === 'tarjeta' && numeroTarjeta.length < 4)} onClick={() => setStep('resumen')}>Continuar</Button>
          </div>
        </Card>
      )}

      {step === 'resumen' && (
        <Card padding="card-pad-lg">
          <div className="text-label" style={{ marginBottom: 14 }}>Resumen de tu compra</div>
          {compraError && (
            <div style={{ marginBottom: 16 }}>
              <Alert tone="error" title={compraErrorTipo === 'error_pasarela' ? 'Error de la pasarela de pago' : 'Pago rechazado'}>
                {compraError}
                {compraErrorTipo === 'error_pasarela' && ' Puedes reintentar sin perder los datos de tu compra.'}
              </Alert>
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
            <Row label="Beneficio" value={convenio.nombre} />
            <Row label="Cantidad" value={`${cantidad} unidad${cantidad > 1 ? 'es' : ''}`} />
            <Row label="Precio unitario" value={formatCOP(convenio.precio_beet)} />
            <Row label="Forma de pago" value={metodoPago === 'tarjeta' ? 'Tarjeta débito/crédito' : `Cupo de la cooperativa · ${cuotasLabel(cuotas)}`} />
            {metodoPago === 'cupo' && <Row label="Cupo disponible después de esta compra" value={formatCOP(cupoDisponible - total)} />}
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingTop: 12, borderTop: '1px solid var(--border-default)' }}>
              <span style={{ fontWeight: 600 }}>Total a pagar</span>
              <span className="tabular" style={{ fontWeight: 600, fontSize: 20 }}>{formatCOP(total)}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <Button variant="secondary" onClick={() => setStep('pago')}>Atrás</Button>
            <Button style={{ flex: 1 }} onClick={confirmarCompra}>Confirmar compra</Button>
          </div>
        </Card>
      )}

      {step === 'confirmando' && (
        <LoadingState title="Procesando tu pago" description="No cierres esta ventana. Estamos asignando tu código." />
      )}

      {step === 'firma' && (
        <Card padding="card-pad-lg">
          <div className="text-label" style={{ marginBottom: 10 }}>Documento de asunción de deuda</div>
          {compraError && (
            <div style={{ marginBottom: 16 }}>
              <Alert tone="error" title="No fue posible completar la compra">{compraError}</Alert>
            </div>
          )}
          <div className="grid grid-2" style={{ marginBottom: 16 }}>
            <Row label="Valor" value={formatCOP(total)} />
            <Row label="Cuotas" value={cuotasLabel(cuotas)} />
          </div>
          <p className="text-small" style={{ background: 'var(--bg-app)', border: '1px solid var(--border-default)', borderRadius: 10, padding: 14 }}>
            El afiliado autoriza a la cooperativa a descontar del cupo de crédito asignado el valor de la compra realizada, en el número de cuotas seleccionado, y reconoce esta obligación como una deuda exigible frente a la entidad.
          </p>
          <div className="text-label" style={{ margin: '18px 0 8px' }}>Firma</div>
          <SignaturePad onChange={setFirmaBase64} />
          <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
            <Button variant="secondary" onClick={() => setStep('resumen')}>Atrás</Button>
            <Button style={{ flex: 1 }} disabled={!firmaBase64} onClick={firmarYConfirmar}>Firmar y confirmar compra</Button>
          </div>
          <button
            onClick={() => navigate(`/portal/catalogo/${convenio.id}`)}
            className="text-small"
            style={{ background: 'none', border: 'none', padding: '8px 4px', margin: '6px -4px 0', cursor: 'pointer', color: 'var(--text-muted)', textDecoration: 'underline', minHeight: 32 }}
          >
            Cancelar compra
          </button>
        </Card>
      )}

      {step === 'resultado' && resultado && (
        <div>
          <Alert tone="success" title="Compra completada">
            Tu {convenio.nombre} quedó registrada y disponible en Mis tickets.
          </Alert>
          <Card padding="card-pad-lg" style={{ marginTop: 18 }}>
            <div className="text-label" style={{ marginBottom: 10 }}>Códigos asignados</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {resultado.codigos.map((c) => (
                <div key={c} style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--bg-app)', border: '1px solid var(--border-default)', borderRadius: 8, padding: '10px 12px' }}>
                  <span className="text-mono" style={{ flex: 1 }}>{c}</span>
                </div>
              ))}
            </div>
          </Card>
          <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
            <Button variant="secondary" onClick={() => navigate('/portal/catalogo')}>Seguir explorando</Button>
            <Button style={{ flex: 1 }} onClick={() => navigate('/portal/tickets')}>Ver mis tickets</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
      <span className="text-small">{label}</span>
      <span style={{ fontWeight: 500, textAlign: 'right' }}>{value}</span>
    </div>
  );
}
