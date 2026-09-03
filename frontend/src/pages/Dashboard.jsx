import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSetBreadcrumbs } from '../components/layout/breadcrumbs';
import { KpiCard, Card } from '../components/ui/Card';
import { ErrorState, LoadingState } from '../components/ui/States';
import { IconWarningTriangle } from '../components/ui/Icons';
import * as dashboardService from '../services/dashboardService';
import * as reportesService from '../services/reportesService';
import { formatCOP, formatDateTime } from '../utils/format';
import { useAuth } from '../context/AuthContext';
import { useCooperativa } from '../context/CooperativaContext';
import RequireCooperativaSeleccionada from '../components/layout/RequireCooperativaSeleccionada';
import { useRecentActivity } from '../hooks/useRecentActivity';

export default function Dashboard() {
  useSetBreadcrumbs([{ label: 'Dashboard' }]);
  const { nombreEntidad } = useAuth();
  const { necesitaSeleccion, selectedId } = useCooperativa();

  const [stats, setStats] = useState(null);
  const [rendimiento, setRendimiento] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { items: actividadReciente, loading: actividadLoading } = useRecentActivity(8);

  const cargar = () => {
    if (necesitaSeleccion) return;
    setLoading(true);
    setError(null);
    Promise.all([dashboardService.obtenerDashboardStats(), reportesService.obtenerRendimientoConvenios()])
      .then(([s, r]) => {
        setStats(s);
        setRendimiento(r.slice(0, 5));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { cargar(); }, [necesitaSeleccion, selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (necesitaSeleccion) {
    return (
      <div>
        <div className="page-header">
          <div>
            <h1 className="text-h1 page-title">Dashboard</h1>
          </div>
        </div>
        <RequireCooperativaSeleccionada />
      </div>
    );
  }

  if (loading) return <LoadingState title="Cargando estadísticas desde PostgreSQL…" />;
  if (error) return <ErrorState description={error} onRetry={cargar} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <span className="text-label">{nombreEntidad}</span>
          <h1 className="text-h1 page-title">Dashboard</h1>
          <p className="page-subtitle">Visibilidad en tiempo real de ventas, redenciones, inventario y ahorro generado a los afiliados.</p>
        </div>
      </div>

      <div className="grid grid-kpi section-gap">
        <KpiCard label="Ventas del mes" value={formatCOP(stats.ventas_del_mes)} delta="Mes en curso" deltaTone="neutral" />
        <KpiCard label="Ahorro generado" value={formatCOP(stats.ahorro_generado)} delta="Acumulado histórico" deltaTone="neutral" />
        <KpiCard
          label="Convenios por vencer"
          value={stats.convenios_por_vencer}
          delta="Vigencia termina en los próximos 30 días"
          deltaTone="warning"
          icon={<IconWarningTriangle size={14} color="var(--warning)" />}
        />
        <KpiCard label="Convenios activos" value={stats.convenios_activos} delta="En catálogo" deltaTone="neutral" />
      </div>

      <div className="grid grid-2 section-gap">
        <Card>
          <div className="text-label" style={{ marginBottom: 14 }}>Ventas por forma de pago</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                <span>Tarjeta débito/crédito</span><span className="tabular" style={{ color: 'var(--text-muted)' }}>{stats.ventas_por_forma_de_pago.pct_tarjeta}%</span>
              </div>
              <div className="progress-track"><div className="progress-fill brand" style={{ width: `${stats.ventas_por_forma_de_pago.pct_tarjeta}%` }} /></div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                <span>Cupo de la cooperativa</span><span className="tabular" style={{ color: 'var(--text-muted)' }}>{stats.ventas_por_forma_de_pago.pct_cupo}%</span>
              </div>
              <div className="progress-track"><div className="progress-fill green" style={{ width: `${stats.ventas_por_forma_de_pago.pct_cupo}%` }} /></div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border-default)' }} className="text-caption">
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--brand-primary)' }} />Tarjeta · {formatCOP(stats.ventas_por_forma_de_pago.tarjeta)}</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--accent-green)' }} />Cupo · {formatCOP(stats.ventas_por_forma_de_pago.cupo)}</span>
          </div>
        </Card>

        <Card>
          <div className="text-label" style={{ marginBottom: 14 }}>Cupo consumido (todos los afiliados)</div>
          <div className="text-small cell-muted" style={{ padding: '8px 0' }}>
            Este agregado todavía no tiene un endpoint dedicado en el backend — se conectará en la fase de cupos/transacciones.
          </div>
        </Card>
      </div>

      <div className="grid detail-grid-2col" style={{ '--col-ratio': '1.3fr 1fr', gap: 16 }}>
        <Card padding="card-pad">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 14 }}>
            <span className="text-label" style={{ marginBottom: 0 }}>Rendimiento por convenio</span>
            <Link to="/reportes" className="text-small" style={{ fontWeight: 600 }}>Ver reportes</Link>
          </div>
          {rendimiento.length === 0 ? (
            <div className="text-small cell-muted">Sin ventas registradas todavía.</div>
          ) : (
            <div className="table-scroll">
              <table className="data-table" style={{ minWidth: 0 }}>
                <thead>
                  <tr>
                    <th>Convenio</th>
                    <th className="right">Unidades vendidas</th>
                    <th className="right">Ingresos</th>
                    <th className="right">Redención</th>
                  </tr>
                </thead>
                <tbody>
                  {rendimiento.map((r) => (
                    <tr key={r.convenio_id}>
                      <td className="cell-primary">{r.convenio_nombre}</td>
                      <td className="right tabular">{r.unidades_vendidas}</td>
                      <td className="right tabular">{formatCOP(r.ingresos)}</td>
                      <td className="right tabular">{r.tasa_redencion}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card padding="card-pad">
          <div className="text-label" style={{ marginBottom: 14 }}>Actividad reciente</div>
          {actividadLoading ? (
            <LoadingState title="Cargando…" />
          ) : actividadReciente.length === 0 ? (
            <div className="text-small cell-muted">Sin actividad registrada todavía.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {actividadReciente.map((a) => (
                <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{a.texto}</div>
                    <div className="text-caption">{a.detalle} · {formatDateTime(a.fecha)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
