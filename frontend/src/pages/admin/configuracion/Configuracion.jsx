import { useCallback, useEffect, useState } from 'react';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import { Card } from '../../../components/ui/Card';
import { Field, Input } from '../../../components/ui/Field';
import Button from '../../../components/ui/Button';
import { ErrorState, LoadingState } from '../../../components/ui/States';
import * as adminService from '../../../services/adminService';
import { useAuth } from '../../../context/AuthContext';
import { useToast } from '../../../context/ToastContext';

// NOTE: unlike an earlier design assumption, the real `cooperativas` table
// only has `nombre`, `nit`, and `estado` — the payment-method toggles and
// the debt-assumption legal text (`tarjeta_habilitada`, `cupo_habilitado`,
// `texto_asuncion_deuda`, `correo_contacto`, `logo_url`) have no backing
// column and are not part of this integration pass (see SCHEMA_NOTES.md).
export default function Configuracion() {
  useSetBreadcrumbs([{ label: 'Configuración' }]);
  const { permissions } = useAuth();
  const { push } = useToast();

  const [coop, setCoop] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const readOnly = !permissions.write;

  const cargar = useCallback(() => {
    setLoading(true);
    setError(null);
    adminService
      .obtenerCooperativa()
      .then(setCoop)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const guardar = async () => {
    setSaving(true);
    try {
      const actualizado = await adminService.actualizarCooperativa({ nombre: coop.nombre });
      setCoop(actualizado);
      push({ title: 'Configuración guardada', description: 'Datos de la entidad actualizados.' });
    } catch (err) {
      push({ title: 'No se pudo guardar', description: err.message, variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState title="Cargando configuración desde PostgreSQL…" />;
  if (error) return <ErrorState description={error} onRetry={cargar} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">Configuración</h1>
          <p className="page-subtitle">Datos de la cooperativa registrados en PostgreSQL.</p>
        </div>
      </div>

      <Card padding="card-pad-lg">
        <div style={{ maxWidth: 560 }}>
          <Field label="Nombre de la cooperativa">
            <Input value={coop.nombre} disabled={readOnly} onChange={(e) => setCoop((v) => ({ ...v, nombre: e.target.value }))} />
          </Field>
          <Field label="NIT" hint="El NIT se configura una sola vez y no se puede editar desde aquí.">
            <Input value={coop.nit} disabled />
          </Field>
          {!readOnly && (
            <Button loading={saving} onClick={guardar}>Guardar cambios</Button>
          )}
        </div>
      </Card>
    </div>
  );
}
