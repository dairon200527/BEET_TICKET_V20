import { useEffect, useState } from 'react';
import { listarLogsAuditoria } from '../services/adminService';
import { useCooperativa } from '../context/CooperativaContext';

// Real recent-activity feed backed by logs_auditoria (GET /api/admin/logs)
// — replaces the old ACTIVIDAD_RECIENTE mock array. Every mutating admin
// action already writes one of these rows (see backend/app/services/audit_service.py),
// so this is genuine, scoped-to-your-cooperativa activity, not a fabricated feed.
const ACCION_LABELS = {
  afiliado_creado: 'Afiliado creado',
  afiliado_actualizado: 'Afiliado actualizado',
  afiliados_carga_masiva: 'Carga masiva de afiliados',
  convenio_creado: 'Convenio creado',
  convenio_actualizado: 'Convenio actualizado',
  plantilla_creada: 'Plantilla creada',
  plantilla_actualizada: 'Plantilla actualizada',
  plantilla_archivo_subido: 'Archivo de plantilla subido',
  inventario_carga_masiva: 'Carga de inventario',
  inventario_bloqueado: 'Inventario bloqueado',
  inventario_desbloqueado: 'Inventario desbloqueado',
  inventario_marcado_vencido: 'Inventario marcado como vencido',
  cupo_actualizado: 'Cupo actualizado',
  cupo_asignacion_masiva: 'Asignación masiva de cupos',
  usuario_admin_creado: 'Usuario administrador creado',
  usuario_admin_actualizado: 'Usuario administrador actualizado',
  cooperativa_actualizada: 'Configuración actualizada',
  compra_completada: 'Compra completada',
};

export function useRecentActivity(limit = 8) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { necesitaSeleccion, selectedId } = useCooperativa();

  useEffect(() => {
    if (necesitaSeleccion) {
      // SUPER_ADMIN with no cooperativa picked yet — nothing to show
      // (the backend would 400), not an error worth surfacing here.
      setItems([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    listarLogsAuditoria({ page: 1, pageSize: limit })
      .then((data) => {
        if (cancelled) return;
        setItems(
          data.items.map((log) => ({
            id: log.id,
            texto: ACCION_LABELS[log.accion] ?? log.accion,
            detalle: `${log.tabla_afectada}${log.registro_id ? ` #${log.registro_id}` : ''}`,
            fecha: log.created_at,
          }))
        );
      })
      .catch((err) => { if (!cancelled) setError(err); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [limit, necesitaSeleccion, selectedId]);

  return { items, loading, error };
}
