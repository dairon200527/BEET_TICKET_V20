import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import { Card, ProgressStatCard } from '../../../components/ui/Card';
import { StatusBadge } from '../../../components/ui/Badge';
import Avatar from '../../../components/ui/Avatar';
import Button from '../../../components/ui/Button';
import { Tabs } from '../../../components/ui/Nav';
import { EmptyState, ErrorState, LoadingState } from '../../../components/ui/States';
import PermissionGate from '../../../components/ui/PermissionGate';
import { ConfirmDialog } from '../../../components/ui/Modal';
import CupoFormModal from '../cupos/CupoFormModal';
import * as afiliadosService from '../../../services/afiliadosService';
import * as cuposService from '../../../services/cuposService';
import { ApiError } from '../../../services/apiClient';
import { formatCOP, percent } from '../../../utils/format';
import { useToast } from '../../../context/ToastContext';

const TABS = [
  { key: 'transacciones', label: 'Transacciones' },
  { key: 'documentos', label: 'Documentos' },
];

export default function AfiliadoDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();

  const [afiliado, setAfiliado] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [cupo, setCupo] = useState(null); // null = no cupo assigned yet (real 404, not an error)
  const [cupoLoading, setCupoLoading] = useState(true);

  const [tab, setTab] = useState('transacciones');
  const [cupoModalOpen, setCupoModalOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [savingEstado, setSavingEstado] = useState(false);

  const cargar = useCallback(() => {
    setLoading(true);
    setError(null);
    afiliadosService
      .obtenerAfiliado(id)
      .then(setAfiliado)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'No pudimos cargar este afiliado.'))
      .finally(() => setLoading(false));

    setCupoLoading(true);
    cuposService
      .obtenerCupo(id)
      .then(setCupo)
      .catch((err) => {
        // A 404 here just means this affiliate has no cupo assigned yet —
        // that's a real, valid state, not an error to surface.
        if (!(err instanceof ApiError && err.status === 404)) push({ title: 'No se pudo cargar el cupo', description: err.message, variant: 'error' });
        setCupo(null);
      })
      .finally(() => setCupoLoading(false));
  }, [id, push]);

  useEffect(() => { cargar(); }, [cargar]);

  const nombreCompleto = afiliado ? `${afiliado.nombres} ${afiliado.apellidos}` : 'Detalle';

  useSetBreadcrumbs([
    { label: 'Afiliados', to: '/afiliados' },
    { label: nombreCompleto },
  ]);

  if (loading) return <LoadingState title="Cargando afiliado desde PostgreSQL…" />;
  if (error) return <ErrorState description={error} onRetry={cargar} />;
  if (!afiliado) {
    return <EmptyState title="Afiliado no encontrado" actionLabel="Volver a afiliados" onAction={() => navigate('/afiliados')} />;
  }

  const toggleEstado = async () => {
    const nuevoEstado = !afiliado.estado;
    setSavingEstado(true);
    try {
      const actualizado = await afiliadosService.actualizarAfiliado(afiliado.id, { estado: nuevoEstado });
      setAfiliado(actualizado);
      push({ title: nuevoEstado ? 'Afiliado reactivado' : 'Afiliado marcado como retirado', description: nombreCompleto });
    } catch (err) {
      push({ title: 'No se pudo actualizar el afiliado', description: err.message, variant: 'error' });
    } finally {
      setSavingEstado(false);
      setConfirmAction(null);
    }
  };

  const guardarCupo = async ({ total }) => {
    try {
      const actualizado = await cuposService.actualizarCupo(afiliado.id, { cupo_total: total });
      setCupo(actualizado);
      push({ title: 'Cupo actualizado', description: `${nombreCompleto} · ${formatCOP(actualizado.cupo_total)}` });
      setCupoModalOpen(false);
    } catch (err) {
      push({ title: 'No se pudo actualizar el cupo', description: err.message, variant: 'error' });
    }
  };

  const usado = cupo ? cupo.cupo_total - cupo.cupo_disponible : 0;

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
          <Avatar name={nombreCompleto} size="md" />
          <div>
            <h1 className="text-h1 page-title" style={{ marginTop: 0 }}>{nombreCompleto}</h1>
            <p className="page-subtitle text-mono">{afiliado.documento} · {afiliado.correo} · {afiliado.telefono ?? 'sin teléfono'}</p>
          </div>
        </div>
        <div className="page-header-actions">
          <StatusBadge status={afiliado.estado} />
          <PermissionGate>
            <Button variant="secondary" loading={savingEstado} onClick={() => setConfirmAction(afiliado.estado ? 'retirar' : 'activar')}>
              {afiliado.estado ? 'Marcar como retirado' : 'Reactivar afiliado'}
            </Button>
          </PermissionGate>
        </div>
      </div>

      <div className="grid detail-grid-2col section-gap" style={{ '--col-ratio': '1fr 1fr', gap: 16 }}>
        {cupoLoading ? (
          <Card><LoadingState title="Cargando cupo…" /></Card>
        ) : cupo ? (
          <ProgressStatCard
            label="Cupo de crédito"
            pct={percent(usado, cupo.cupo_total)}
            usedLabel={`Usado ${formatCOP(usado)}`}
            availableLabel={`Disponible ${formatCOP(cupo.cupo_disponible)}`}
          />
        ) : (
          <Card>
            <EmptyState title="Sin cupo de crédito asignado" description="Asigna un cupo para que el afiliado pueda comprar con crédito de la cooperativa." />
          </Card>
        )}
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <div className="text-label">Estado del cupo</div>
              {cupo ? (
                <>
                  <div style={{ fontSize: 15, fontWeight: 600, marginTop: 4 }}>{formatCOP(cupo.cupo_total)}</div>
                  <StatusBadge status={cupo.estado} />
                </>
              ) : (
                <div className="text-small cell-muted" style={{ marginTop: 4 }}>No asignado</div>
              )}
            </div>
            <PermissionGate>
              <Button size="sm" variant="secondary" onClick={() => setCupoModalOpen(true)}>{cupo ? 'Editar cupo' : 'Asignar cupo'}</Button>
            </PermissionGate>
          </div>
        </Card>
      </div>

      <Card padding="card-pad-lg">
        <Tabs items={TABS} active={tab} onChange={setTab} />
        <div style={{ marginTop: 18 }}>
          {tab === 'transacciones' && (
            <EmptyState
              title="Conexión pendiente para esta sección"
              description="Este afiliado no tiene un endpoint propio de transacciones — consulta el listado general en Transacciones y filtra por este afiliado."
            />
          )}
          {tab === 'documentos' && (
            <EmptyState
              title="Conexión pendiente para esta sección"
              description="Este afiliado no tiene un endpoint propio de documentos — consulta el listado general en Transacciones › Documentos."
            />
          )}
        </div>
      </Card>

      <CupoFormModal
        open={cupoModalOpen}
        onClose={() => setCupoModalOpen(false)}
        afiliado={{ ...afiliado, cupo: { total: cupo?.cupo_total ?? 0 } }}
        onSave={guardarCupo}
      />

      <ConfirmDialog
        open={!!confirmAction}
        onClose={() => setConfirmAction(null)}
        title={confirmAction === 'retirar' ? `¿Marcar a ${nombreCompleto} como retirado?` : `¿Reactivar a ${nombreCompleto}?`}
        description={confirmAction === 'retirar'
          ? 'El afiliado deja de poder comprar beneficios hasta que sea reactivado. Las compras ya realizadas no se modifican.'
          : 'El afiliado vuelve a poder comprar beneficios en el catálogo.'}
        confirmLabel={confirmAction === 'retirar' ? 'Marcar como retirado' : 'Reactivar'}
        tone={confirmAction === 'retirar' ? 'danger' : 'info'}
        loading={savingEstado}
        onConfirm={toggleEstado}
      />
    </div>
  );
}
