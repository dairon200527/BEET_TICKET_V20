import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import { Card, KpiCard } from '../../../components/ui/Card';
import { Select } from '../../../components/ui/Field';
import Button from '../../../components/ui/Button';
import { IconDescargar } from '../../../components/ui/Icons';
import { ErrorState, LoadingState } from '../../../components/ui/States';
import * as dashboardService from '../../../services/dashboardService';
import * as reportesService from '../../../services/reportesService';
import * as convenioService from '../../../services/convenioService';
import { formatCOP } from '../../../utils/format';
import { useToast } from '../../../context/ToastContext';
import { useCooperativa } from '../../../context/CooperativaContext';
import RequireCooperativaSeleccionada from '../../../components/layout/RequireCooperativaSeleccionada';

export default function Reportes() {
  useSetBreadcrumbs([{ label: 'Reportes' }]);
  const { push } = useToast();
  const { necesitaSeleccion, selectedId, selected, isSuperAdmin } = useCooperativa();
  const [filtros, setFiltros] = useState({ convenio: '', metodoPago: '', estado: '' });

  const [stats, setStats] = useState(null);
  const [rendimiento, setRendimiento] = useState([]);
  const [convenios, setConvenios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const cargar = useCallback(() => {
    if (necesitaSeleccion) return;
    setLoading(true);
    setError(null);
    Promise.all([
      dashboardService.obtenerDashboardStats(),
      reportesService.obtenerRendimientoConvenios(),
      convenioService.listarConvenios({ pageSize: 100 }),
    ])
      .then(([s, r, c]) => {
        setStats(s);
        setRendimiento(r);
        setConvenios(c.items);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [necesitaSeleccion]);

  useEffect(() => { cargar(); }, [cargar, selectedId]);

  // BUG FIX: `filtros.convenio` was set by the Select below but never
  // actually applied anywhere — the table always rendered the full,
  // unfiltered `rendimiento` array regardless of what was selected,
  // which reads exactly like "wrong convenio's data" when in fact NO
  // filtering was ever happening at all.
  const rendimientoFiltrado = useMemo(
    () => (filtros.convenio ? rendimiento.filter((r) => String(r.convenio_id) === String(filtros.convenio)) : rendimiento),
    [rendimiento, filtros.convenio]
  );

  const [exportando, setExportando] = useState(null); // 'rendimiento' | 'afiliados' | null

  const descargar = (blob, filename) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  const exportar = async (reporte) => {
    setExportando(reporte);
    try {
      const { blob, filename } = reporte === 'afiliados'
        ? await reportesService.exportarAfiliados()
        : await reportesService.exportarRendimientoConvenios();
      descargar(blob, filename);
      push({ title: 'Reporte exportado', description: filename });
    } catch (err) {
      push({ title: 'No se pudo exportar el reporte', description: err.message, variant: 'error' });
    } finally {
      setExportando(null);
    }
  };

  if (necesitaSeleccion) {
    return (
      <div>
        <div className="page-header">
          <div><h1 className="text-h1 page-title">Reportes</h1></div>
        </div>
        <RequireCooperativaSeleccionada />
      </div>
    );
  }

  if (loading) return <LoadingState title="Cargando reportes desde PostgreSQL…" />;
  if (error) return <ErrorState description={error} onRetry={cargar} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">Reportes</h1>
          <p className="page-subtitle">Ventas, redenciones, inventario y métodos de pago, con datos reales de PostgreSQL.</p>
          {isSuperAdmin && selected && (
            <p className="text-caption" style={{ marginTop: 4 }}>Estás gestionando datos de: {selected.nombre}</p>
          )}
        </div>
        <div className="page-header-actions">
          <Button
            variant="secondary"
            icon={<IconDescargar size={15} color="#1F2937" />}
            loading={exportando === 'rendimiento'}
            onClick={() => exportar('rendimiento')}
          >
            Exportar rendimiento
          </Button>
          <Button
            variant="secondary"
            icon={<IconDescargar size={15} color="#1F2937" />}
            loading={exportando === 'afiliados'}
            onClick={() => exportar('afiliados')}
          >
            Exportar afiliados
          </Button>
        </div>
      </div>

      <Card padding="card-pad" className="section-gap">
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Select style={{ width: 200 }} value={filtros.convenio} onChange={(e) => setFiltros((f) => ({ ...f, convenio: e.target.value }))}>
            <option value="">Todo convenio</option>
            {convenios.map((c) => <option key={c.id} value={c.id}>{c.nombre}{!c.estado ? ' (inactivo)' : ''}</option>)}
          </Select>
          <Select style={{ width: 150 }} value={filtros.metodoPago} onChange={(e) => setFiltros((f) => ({ ...f, metodoPago: e.target.value }))}>
            <option value="">Todo pago</option>
            <option value="TARJETA">Tarjeta</option>
            <option value="CUPO">Cupo</option>
          </Select>
          <Select style={{ width: 150 }} value={filtros.estado} onChange={(e) => setFiltros((f) => ({ ...f, estado: e.target.value }))}>
            <option value="">Todo estado</option>
            <option value="PENDIENTE">Pendiente</option>
            <option value="APROBADA">Aprobada</option>
            <option value="RECHAZADA">Rechazada</option>
            <option value="CANCELADA">Cancelada</option>
            <option value="COMPLETADA">Completada</option>
          </Select>
        </div>
      </Card>

      <div className="grid grid-kpi section-gap">
        <KpiCard label="Ventas del mes" value={formatCOP(stats.ventas_del_mes)} deltaTone="neutral" delta="Mes en curso" />
        <KpiCard label="Ahorro generado" value={formatCOP(stats.ahorro_generado)} deltaTone="neutral" delta="Acumulado histórico" />
        <KpiCard label="Tarjeta vs. cupo" value={`${stats.ventas_por_forma_de_pago.pct_tarjeta}% / ${stats.ventas_por_forma_de_pago.pct_cupo}%`} deltaTone="neutral" delta="Distribución de ventas" />
        <KpiCard label="Convenios activos" value={stats.convenios_activos} deltaTone="neutral" delta="En catálogo" />
      </div>

      <Card padding="card-pad-lg">
        <div className="text-label" style={{ marginBottom: 14 }}>Rendimiento por convenio</div>
        {rendimientoFiltrado.length === 0 ? (
          <div className="text-small cell-muted">
            {filtros.convenio ? 'Este convenio no tiene ventas registradas todavía.' : 'Sin ventas registradas todavía.'}
          </div>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Convenio</th>
                  <th className="right">Vendidas</th>
                  <th className="right">Ingresos</th>
                  <th className="right">Disponible</th>
                  <th className="right">Entregada</th>
                  <th className="right">Tasa de redención</th>
                </tr>
              </thead>
              <tbody>
                {rendimientoFiltrado.map((r) => (
                  <tr key={r.convenio_id}>
                    <td className="cell-primary">{r.convenio_nombre}</td>
                    <td className="right tabular">{r.unidades_vendidas}</td>
                    <td className="right tabular">{formatCOP(r.ingresos)}</td>
                    <td className="right tabular">{r.disponible}</td>
                    <td className="right tabular">{r.entregada}</td>
                    <td className="right tabular">{r.tasa_redencion}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
