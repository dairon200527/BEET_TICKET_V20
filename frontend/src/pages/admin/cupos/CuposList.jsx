import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import Button from '../../../components/ui/Button';
import { Input, Select } from '../../../components/ui/Field';
import { IconBuscar } from '../../../components/ui/Icons';
import { Pagination, Dropdown } from '../../../components/ui/Nav';
import { StatusBadge } from '../../../components/ui/Badge';
import Avatar from '../../../components/ui/Avatar';
import { EmptyState, ErrorState, LoadingState } from '../../../components/ui/States';
import Modal from '../../../components/ui/Modal';
import { ConfirmDialog } from '../../../components/ui/Modal';
import { Field, Input as FieldInput } from '../../../components/ui/Field';
import PermissionGate from '../../../components/ui/PermissionGate';
import CupoFormModal from './CupoFormModal';
import { useTableState } from '../../../hooks/useTableState';
import * as afiliadosService from '../../../services/afiliadosService';
import * as cuposService from '../../../services/cuposService';
import { ApiError } from '../../../services/apiClient';
import { formatCOP, percent } from '../../../utils/format';
import { useToast } from '../../../context/ToastContext';
import { useCooperativa } from '../../../context/CooperativaContext';
import RequireCooperativaSeleccionada from '../../../components/layout/RequireCooperativaSeleccionada';

// NOTE: unlike an earlier design assumption, `cupos_credito` has no
// `periodicidad` column in the real schema, and `cupo_disponible` stores
// the remaining balance DIRECTLY (used = cupo_total - cupo_disponible) —
// see backend/app/models/cupo_credito.py / SCHEMA_NOTES.md.
export default function CuposList() {
  useSetBreadcrumbs([{ label: 'Cupos de crédito' }]);
  const { push } = useToast();
  const { necesitaSeleccion, selectedId, selected, isSuperAdmin } = useCooperativa();

  const [filas, setFilas] = useState([]); // afiliado + cupo (or null) merged, real data only
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [editTarget, setEditTarget] = useState(null);
  const [suspendTarget, setSuspendTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [masivoOpen, setMasivoOpen] = useState(false);

  const cargar = useCallback(() => {
    if (necesitaSeleccion) return;
    setLoading(true);
    setError(null);
    afiliadosService
      .listarAfiliados({ pageSize: 100 })
      .then((data) =>
        Promise.all(
          data.items.map((a) =>
            cuposService
              .obtenerCupo(a.id)
              .then((cupo) => ({ ...a, cupo }))
              .catch(() => ({ ...a, cupo: null }))
          )
        )
      )
      .then(setFilas)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'No pudimos cargar los cupos.'))
      .finally(() => setLoading(false));
  }, [necesitaSeleccion]);

  useEffect(() => { cargar(); }, [cargar, selectedId]);

  const { search, setSearch, filters, setFilter, pageRows, page, setPage, totalPages, total } = useTableState({
    data: filas.map((a) => ({ ...a, estadoCupo: a.cupo?.estado })),
    searchFields: ['nombres', 'apellidos', 'documento'],
    pageSize: 10,
  });

  const guardarCupo = async ({ total: cupo_total }) => {
    try {
      const cupo = await cuposService.actualizarCupo(editTarget.id, { cupo_total });
      setFilas((prev) => prev.map((a) => (a.id === editTarget.id ? { ...a, cupo } : a)));
      push({ title: 'Cupo actualizado', description: `${editTarget.nombres} ${editTarget.apellidos} · ${formatCOP(cupo.cupo_total)}` });
      setEditTarget(null);
    } catch (err) {
      push({ title: 'No se pudo actualizar el cupo', description: err.message, variant: 'error' });
    }
  };

  const toggleSuspendido = async () => {
    const nuevoEstado = !suspendTarget.cupo.estado;
    try {
      const cupo = await cuposService.actualizarCupo(suspendTarget.id, { estado: nuevoEstado });
      setFilas((prev) => prev.map((a) => (a.id === suspendTarget.id ? { ...a, cupo } : a)));
      push({ title: nuevoEstado ? 'Cupo reactivado' : 'Cupo suspendido', description: `${suspendTarget.nombres} ${suspendTarget.apellidos}` });
    } catch (err) {
      push({ title: 'No se pudo actualizar el cupo', description: err.message, variant: 'error' });
    } finally {
      setSuspendTarget(null);
    }
  };

  const eliminarCupo = async () => {
    try {
      // The backend has no cupo-delete endpoint — this zeroes the assigned
      // amount and suspends it, the closest real equivalent.
      const cupo = await cuposService.actualizarCupo(deleteTarget.id, { cupo_total: 0, cupo_disponible: 0, estado: false });
      setFilas((prev) => prev.map((a) => (a.id === deleteTarget.id ? { ...a, cupo } : a)));
      push({ title: 'Cupo eliminado', description: `${deleteTarget.nombres} ${deleteTarget.apellidos}`, variant: 'error' });
    } catch (err) {
      push({ title: 'No se pudo eliminar el cupo', description: err.message, variant: 'error' });
    } finally {
      setDeleteTarget(null);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">Cupos de crédito</h1>
          <p className="page-subtitle">Monto y consumo del cupo que la cooperativa asigna a cada afiliado, desde PostgreSQL.</p>
          {isSuperAdmin && (
            <p className="text-caption" style={{ marginTop: 4 }}>
              {selected ? `Estás gestionando datos de: ${selected.nombre}` : 'Selecciona una cooperativa arriba para empezar.'}
            </p>
          )}
        </div>
        <div className="page-header-actions">
          <PermissionGate>
            <Button variant="secondary" onClick={() => setMasivoOpen(true)} disabled={necesitaSeleccion}>Asignación masiva</Button>
          </PermissionGate>
        </div>
      </div>

      {necesitaSeleccion ? (
        <RequireCooperativaSeleccionada />
      ) : (
      <div className="table-card">
        <div className="table-toolbar">
          <div className="table-toolbar-left">
            <label className="input-affix-wrap" style={{ width: 260 }}>
              <span className="input-affix-icon"><IconBuscar size={16} color="var(--text-muted)" /></span>
              <Input placeholder="Buscar por nombre o documento" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
            <Select
              style={{ width: 170 }}
              value={filters.estadoCupo === undefined ? '' : String(filters.estadoCupo)}
              onChange={(e) => setFilter('estadoCupo', e.target.value === '' ? undefined : e.target.value === 'true')}
            >
              <option value="">Todo estado de cupo</option>
              <option value="true">Activo</option>
              <option value="false">Suspendido</option>
            </Select>
          </div>
        </div>

        {loading ? (
          <LoadingState title="Cargando cupos desde PostgreSQL…" />
        ) : error ? (
          <ErrorState description={error} onRetry={cargar} />
        ) : pageRows.length === 0 ? (
          total === 0 ? (
            <EmptyState title="No hay afiliados registrados" description="Crea afiliados primero para poder asignarles un cupo." />
          ) : (
            <EmptyState title="Sin cupos que coincidan" description="Ajusta los filtros o el término de búsqueda." />
          )
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Afiliado</th>
                  <th className="right">Cupo total</th>
                  <th>Consumo</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((a) => {
                  const usado = a.cupo ? a.cupo.cupo_total - a.cupo.cupo_disponible : 0;
                  return (
                  <tr key={a.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Avatar name={`${a.nombres} ${a.apellidos}`} size="sm" />
                        <div>
                          <div style={{ fontWeight: 500 }}>{a.nombres} {a.apellidos}</div>
                          <div className="cell-muted text-mono">{a.documento}</div>
                        </div>
                      </div>
                    </td>
                    {a.cupo ? (
                      <>
                        <td className="right tabular">{formatCOP(a.cupo.cupo_total)}</td>
                        <td style={{ minWidth: 160 }}>
                          <div className="progress-track thin" style={{ marginBottom: 4 }}>
                            <div className="progress-fill green" style={{ width: `${percent(usado, a.cupo.cupo_total)}%` }} />
                          </div>
                          <div className="cell-muted">{percent(usado, a.cupo.cupo_total)}% usado</div>
                        </td>
                        <td><StatusBadge status={a.cupo.estado} /></td>
                      </>
                    ) : (
                      <td colSpan={2} className="text-small cell-muted">Sin cupo asignado</td>
                    )}
                    <td className="right" style={{ position: 'relative' }}>
                      <PermissionGate fallback={<Link to={`/afiliados/${a.id}`} style={{ fontSize: 13, fontWeight: 600 }}>Ver</Link>}>
                        <Button size="sm" variant="secondary" onClick={() => setOpenMenuId(openMenuId === a.id ? null : a.id)}>Gestionar</Button>
                        <Dropdown
                          open={openMenuId === a.id}
                          onClose={() => setOpenMenuId(null)}
                          style={{ top: 40, right: 0 }}
                          items={[
                            { label: a.cupo ? 'Editar cupo' : 'Asignar cupo', onClick: () => setEditTarget(a) },
                            ...(a.cupo
                              ? [
                                  { label: a.cupo.estado ? 'Suspender cupo' : 'Reactivar cupo', onClick: () => setSuspendTarget(a) },
                                  { divider: true },
                                  { label: 'Eliminar cupo', danger: true, onClick: () => setDeleteTarget(a) },
                                ]
                              : []),
                          ]}
                        />
                      </PermissionGate>
                    </td>
                  </tr>
                );})}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && (
          <Pagination page={page} totalPages={totalPages} onChange={setPage} totalLabel={`Mostrando ${pageRows.length} de ${total} afiliados`} />
        )}
      </div>
      )}

      <CupoFormModal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        afiliado={editTarget ? { ...editTarget, cupo: { total: editTarget.cupo?.cupo_total ?? 0 } } : null}
        onSave={guardarCupo}
      />

      <ConfirmDialog
        open={!!suspendTarget}
        onClose={() => setSuspendTarget(null)}
        tone={suspendTarget?.cupo?.estado ? 'danger' : 'info'}
        title={suspendTarget ? `¿${suspendTarget.cupo.estado ? 'Suspender' : 'Reactivar'} el cupo de ${suspendTarget.nombres} ${suspendTarget.apellidos}?` : ''}
        description="El afiliado no podrá pagar con cupo de la cooperativa mientras esté suspendido. Las compras ya realizadas y sus cuotas no se modifican."
        confirmLabel={suspendTarget?.cupo?.estado ? 'Suspender cupo' : 'Reactivar cupo'}
        onConfirm={toggleSuspendido}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={deleteTarget ? `¿Eliminar el cupo de ${deleteTarget.nombres} ${deleteTarget.apellidos}?` : ''}
        description="El afiliado no podrá pagar con cupo de la cooperativa. Las compras ya realizadas y sus cuotas no se modifican."
        confirmLabel="Eliminar cupo"
        onConfirm={eliminarCupo}
      />

      <AsignacionMasivaModal open={masivoOpen} onClose={() => setMasivoOpen(false)} afiliados={filas} onDone={cargar} />
    </div>
  );
}

function AsignacionMasivaModal({ open, onClose, afiliados, onDone }) {
  const { push } = useToast();
  const [monto, setMonto] = useState(500000);
  const [criterio, setCriterio] = useState('todos');
  const [saving, setSaving] = useState(false);

  const asignar = async () => {
    const objetivo = afiliados.filter((a) => a.estado && (criterio === 'todos' || !a.cupo));
    if (objetivo.length === 0) {
      push({ title: 'Nada que asignar', description: 'No hay afiliados que coincidan con el criterio seleccionado.', variant: 'error' });
      return;
    }
    setSaving(true);
    try {
      const result = await cuposService.asignacionMasivaCupo({
        afiliado_ids: objetivo.map((a) => a.id),
        cupo_total: Number(monto),
      });
      push({ title: 'Cupo asignado de forma masiva', description: result.detail });
      onDone();
      onClose();
    } catch (err) {
      push({ title: 'No se pudo asignar el cupo', description: err.message, variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={() => !saving && onClose()}
      title="Asignación masiva de cupo"
      actions={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving}>Cancelar</Button>
          <Button onClick={asignar} loading={saving}>Asignar cupo</Button>
        </>
      }
    >
      <Field label="Aplicar a">
        <Select value={criterio} onChange={(e) => setCriterio(e.target.value)}>
          <option value="todos">Todos los afiliados activos</option>
          <option value="sin-cupo">Afiliados activos sin cupo asignado</option>
        </Select>
      </Field>
      <Field label="Monto del cupo">
        <FieldInput type="number" min="0" step="10000" value={monto} onChange={(e) => setMonto(e.target.value)} />
      </Field>
    </Modal>
  );
}
