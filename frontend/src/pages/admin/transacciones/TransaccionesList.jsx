import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import Button from '../../../components/ui/Button';
import { Input, Select } from '../../../components/ui/Field';
import { IconBuscar, IconDescargar } from '../../../components/ui/Icons';
import { Pagination } from '../../../components/ui/Nav';
import { StatusBadge } from '../../../components/ui/Badge';
import Avatar from '../../../components/ui/Avatar';
import { EmptyState, ErrorState, LoadingState } from '../../../components/ui/States';
import { useTableState } from '../../../hooks/useTableState';
import * as transaccionesService from '../../../services/transaccionesService';
import * as afiliadosService from '../../../services/afiliadosService';
import * as convenioService from '../../../services/convenioService';
import { ApiError } from '../../../services/apiClient';
import { formatCOP, cuotasLabel } from '../../../utils/format';
import { useCooperativa } from '../../../context/CooperativaContext';
import RequireCooperativaSeleccionada from '../../../components/layout/RequireCooperativaSeleccionada';

export default function TransaccionesList() {
  useSetBreadcrumbs([{ label: 'Transacciones' }]);
  const { necesitaSeleccion, selectedId, selected, isSuperAdmin } = useCooperativa();

  const [transacciones, setTransacciones] = useState([]);
  const [afiliadosPorId, setAfiliadosPorId] = useState({});
  const [conveniosPorId, setConveniosPorId] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const cargar = useCallback(() => {
    if (necesitaSeleccion) return;
    setLoading(true);
    setError(null);
    Promise.all([
      transaccionesService.listarTransacciones({ pageSize: 100 }),
      afiliadosService.listarAfiliados({ pageSize: 100 }),
      convenioService.listarConvenios({ pageSize: 100 }),
    ])
      .then(([trxData, afiliadosData, conveniosData]) => {
        setTransacciones(trxData.items);
        setAfiliadosPorId(Object.fromEntries(afiliadosData.items.map((a) => [a.id, a])));
        setConveniosPorId(Object.fromEntries(conveniosData.items.map((c) => [c.id, c])));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'No pudimos cargar las transacciones.'))
      .finally(() => setLoading(false));
  }, [necesitaSeleccion]);

  useEffect(() => { cargar(); }, [cargar, selectedId]);

  const rows = useMemo(
    () =>
      transacciones.map((t) => {
        const afiliado = afiliadosPorId[t.afiliado_id];
        const convenio = conveniosPorId[t.convenio_id];
        return {
          ...t,
          afiliadoNombre: afiliado ? `${afiliado.nombres} ${afiliado.apellidos}` : undefined,
          afiliadoDocumento: afiliado?.documento,
          convenioNombre: convenio?.nombre,
        };
      }),
    [transacciones, afiliadosPorId, conveniosPorId]
  );

  const convenios = Object.values(conveniosPorId);

  const { search, setSearch, filters, setFilter, pageRows, page, setPage, totalPages, total } = useTableState({
    data: rows,
    searchFields: ['id', 'afiliadoNombre', 'afiliadoDocumento', 'convenioNombre'],
    pageSize: 10,
  });

  if (necesitaSeleccion) {
    return (
      <div>
        <div className="page-header">
          <div><h1 className="text-h1 page-title">Transacciones</h1></div>
        </div>
        <RequireCooperativaSeleccionada />
      </div>
    );
  }

  if (loading) return <LoadingState title="Cargando transacciones desde PostgreSQL…" />;
  if (error) return <ErrorState description={error} onRetry={cargar} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">Transacciones</h1>
          <p className="page-subtitle">Ventas y redenciones registradas en PostgreSQL, por convenio, periodo y afiliado.</p>
          {isSuperAdmin && selected && (
            <p className="text-caption" style={{ marginTop: 4 }}>Estás gestionando datos de: {selected.nombre}</p>
          )}
        </div>
        <div className="page-header-actions">
          <Button variant="secondary" icon={<IconDescargar size={15} color="#1F2937" />}>Exportar</Button>
        </div>
      </div>

      <div className="table-card">
        <div className="table-toolbar">
          <div className="table-toolbar-left">
            <label className="input-affix-wrap" style={{ width: 280 }}>
              <span className="input-affix-icon"><IconBuscar size={16} color="var(--text-muted)" /></span>
              <Input placeholder="Buscar por afiliado, convenio o ID" value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
            <Select style={{ width: 170 }} value={filters.convenio_id ?? ''} onChange={(e) => setFilter('convenio_id', e.target.value)}>
              <option value="">Todo convenio</option>
              {convenios.map((c) => <option key={c.id} value={c.id}>{c.nombre}{!c.estado ? ' (inactivo)' : ''}</option>)}
            </Select>
            <Select style={{ width: 150 }} value={filters.metodo_pago ?? ''} onChange={(e) => setFilter('metodo_pago', e.target.value)}>
              <option value="">Todo pago</option>
              <option value="TARJETA">Tarjeta</option>
              <option value="CUPO">Cupo</option>
            </Select>
            <Select style={{ width: 150 }} value={filters.estado ?? ''} onChange={(e) => setFilter('estado', e.target.value)}>
              <option value="">Todo estado</option>
              <option value="PENDIENTE">Pendiente</option>
              <option value="APROBADA">Aprobada</option>
              <option value="RECHAZADA">Rechazada</option>
              <option value="CANCELADA">Cancelada</option>
              <option value="COMPLETADA">Completada</option>
            </Select>
          </div>
        </div>

        {pageRows.length === 0 ? (
          total === 0 ? (
            <EmptyState title="No hay transacciones registradas" description="Las compras que hagan los afiliados aparecerán aquí." />
          ) : (
            <EmptyState title="Sin transacciones que coincidan" description="Ajusta los filtros o el término de búsqueda." />
          )
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Afiliado</th>
                  <th>Convenio</th>
                  <th>Pago</th>
                  <th className="right">Valor</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((t) => (
                  <tr key={t.id}>
                    <td className="text-mono cell-muted">{t.id}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Avatar name={t.afiliadoNombre ?? '—'} size="sm" />
                        <div>
                          <div style={{ fontWeight: 500 }}>{t.afiliadoNombre ?? '—'}</div>
                          <div className="cell-muted text-mono">{t.afiliadoDocumento}</div>
                        </div>
                      </div>
                    </td>
                    <td>{t.convenioNombre ?? '—'}<div className="cell-muted">{t.cantidad} unidad{t.cantidad > 1 ? 'es' : ''}</div></td>
                    <td className="text-small">
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 8, height: 8, borderRadius: 2, background: t.metodo_pago === 'TARJETA' ? 'var(--brand-primary)' : 'var(--accent-green)' }} />
                        {t.metodo_pago === 'TARJETA' ? 'Tarjeta débito' : `Cupo · ${cuotasLabel(t.numero_cuotas)}`}
                      </span>
                    </td>
                    <td className="right tabular" style={{ fontWeight: 500 }}>{formatCOP(t.total)}</td>
                    <td><StatusBadge status={t.estado} /></td>
                    <td className="right"><Link to={`/transacciones/${t.id}`} style={{ fontSize: 13, fontWeight: 600 }}>Ver</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <Pagination page={page} totalPages={totalPages} onChange={setPage} totalLabel={`Mostrando ${pageRows.length} de ${total} transacciones`} />
      </div>
    </div>
  );
}
