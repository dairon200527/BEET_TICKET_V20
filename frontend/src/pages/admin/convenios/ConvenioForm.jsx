import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useSetBreadcrumbs } from '../../../components/layout/breadcrumbs';
import { Card } from '../../../components/ui/Card';
import { Field, Input, Textarea, Switch } from '../../../components/ui/Field';
import Button from '../../../components/ui/Button';
import Alert from '../../../components/ui/Alert';
import { LoadingState } from '../../../components/ui/States';
import { RequireWriteAccess } from '../../../components/ui/PermissionGate';
import * as convenioService from '../../../services/convenioService';
import { ApiError } from '../../../services/apiClient';
import { formatCOP } from '../../../utils/format';
import { useToast } from '../../../context/ToastContext';

// NOTE: unlike an earlier design assumption, the real `convenios` table
// has no `marca`, `categoria`, `tope`, or `tope_periodicidad` columns —
// this form only edits what the real schema actually stores (see
// SCHEMA_NOTES.md): nombre, descripcion, precios, fecha_inicio/fecha_fin,
// estado.
const emptyForm = {
  nombre: '',
  descripcion: '',
  precio_publico: '',
  precio_beet: '',
  fecha_inicio: '',
  fecha_fin: '',
  activo: true,
};

export default function ConvenioForm() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();
  const { push } = useToast();

  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});
  const [nombreConvenio, setNombreConvenio] = useState('');

  useSetBreadcrumbs([
    { label: 'Convenios', to: '/convenios' },
    { label: isEdit ? nombreConvenio || 'Editar' : 'Crear convenio' },
  ]);

  useEffect(() => {
    if (!isEdit) return;
    convenioService
      .obtenerConvenio(id)
      .then((c) => {
        setForm({
          nombre: c.nombre,
          descripcion: c.descripcion ?? '',
          precio_publico: String(c.precio_publico),
          precio_beet: String(c.precio_beet),
          fecha_inicio: c.fecha_inicio,
          fecha_fin: c.fecha_fin ?? '',
          activo: c.estado,
        });
        setNombreConvenio(c.nombre);
      })
      .catch((err) => push({ title: 'No se pudo cargar el convenio', description: err.message, variant: 'error' }))
      .finally(() => setLoading(false));
  }, [id, isEdit, push]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const ahorro = form.precio_publico && form.precio_beet ? Number(form.precio_publico) - Number(form.precio_beet) : null;
  const ahorroPct = ahorro && form.precio_publico ? Math.round((ahorro / Number(form.precio_publico)) * 100) : null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const nextErrors = {};
    if (!form.nombre.trim()) nextErrors.nombre = 'El nombre del convenio es obligatorio.';
    if (!form.precio_publico) nextErrors.precio_publico = 'Ingresa el precio público.';
    if (!form.precio_beet) nextErrors.precio_beet = 'Ingresa el precio BEET.';
    if (Number(form.precio_beet) > Number(form.precio_publico) && form.precio_publico && form.precio_beet) {
      nextErrors.precio_beet = 'El precio BEET no puede ser mayor al precio público.';
    }
    if (!form.fecha_inicio) nextErrors.fecha_inicio = 'Define la fecha de inicio.';
    if (form.fecha_fin && form.fecha_inicio && form.fecha_fin < form.fecha_inicio) {
      nextErrors.fecha_fin = 'La fecha de fin no puede ser anterior a la de inicio.';
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    const payload = {
      nombre: form.nombre.trim(),
      descripcion: form.descripcion.trim() || null,
      precio_publico: Number(form.precio_publico),
      precio_beet: Number(form.precio_beet),
      fecha_inicio: form.fecha_inicio,
      fecha_fin: form.fecha_fin || null,
      estado: form.activo,
    };

    setSaving(true);
    try {
      if (isEdit) {
        await convenioService.actualizarConvenio(id, payload);
      } else {
        await convenioService.crearConvenio(payload);
      }
      push({ title: isEdit ? 'Convenio actualizado' : 'Convenio creado', description: `${payload.nombre} se guardó en PostgreSQL.` });
      navigate('/convenios');
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && Array.isArray(err.detail)) {
        push({ title: 'Revisa los datos del formulario', description: err.detail.map((d) => d.msg).join(' · '), variant: 'error' });
      } else {
        push({ title: 'No se pudo guardar el convenio', description: err.message, variant: 'error' });
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState title="Cargando convenio…" />;

  return (
    <RequireWriteAccess>
      <div>
        <div className="page-header">
          <div>
            <h1 className="text-h1 page-title">{isEdit ? 'Editar convenio' : 'Crear convenio'}</h1>
            <p className="page-subtitle">Nombre, precios, descripción y vigencia visibles en el catálogo del afiliado.</p>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <Card padding="card-pad-lg" className="section-gap">
            <div className="grid grid-2">
              <div>
                <Field label="Nombre del convenio" error={errors.nombre}>
                  <Input value={form.nombre} onChange={set('nombre')} placeholder="Ej. Cine Colombia" />
                </Field>
                <Field label="Fecha de inicio" error={errors.fecha_inicio}>
                  <Input type="date" value={form.fecha_inicio} onChange={set('fecha_inicio')} />
                </Field>
                <Field label="Fecha de fin" optional error={errors.fecha_fin} hint="Déjalo vacío si el convenio no tiene fecha de vencimiento.">
                  <Input type="date" value={form.fecha_fin} onChange={set('fecha_fin')} />
                </Field>
              </div>
              <div>
                <Field label="Precio público" error={errors.precio_publico}>
                  <Input type="number" min="0" value={form.precio_publico} onChange={set('precio_publico')} placeholder="38000" />
                </Field>
                <Field label="Precio BEET" error={errors.precio_beet} hint={ahorro ? `Ahorro para el afiliado: ${formatCOP(ahorro)} (${ahorroPct}%)` : undefined}>
                  <Input type="number" min="0" value={form.precio_beet} onChange={set('precio_beet')} placeholder="27500" />
                </Field>
                <Field label="Descripción" optional>
                  <Textarea value={form.descripcion} onChange={set('descripcion')} placeholder="Válido de lunes a viernes. No acumulable con otras promociones." />
                </Field>
              </div>
            </div>

            <div style={{ marginTop: 8, paddingTop: 20, borderTop: '1px solid var(--border-default)' }}>
              <Switch
                label="Convenio activo en catálogo"
                checked={form.activo}
                onChange={(e) => setForm((f) => ({ ...f, activo: e.target.checked }))}
              />
            </div>
          </Card>

          <Alert tone="info" title="La plantilla de este convenio se administra por separado">
            Desde aquí solo se configuran los datos comerciales. El código, QR y estado de cada unidad se cargan luego desde Inventario.
          </Alert>

          <div className="page-header-actions" style={{ justifyContent: 'flex-end', marginTop: 24 }}>
            <Button variant="secondary" type="button" onClick={() => navigate('/convenios')} disabled={saving}>Cancelar</Button>
            <Button type="submit" loading={saving}>{isEdit ? 'Guardar cambios' : 'Crear convenio'}</Button>
          </div>
        </form>
      </div>
    </RequireWriteAccess>
  );
}
