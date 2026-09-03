import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAffiliateAuth } from '../../context/AffiliateAuthContext';
import { useToast } from '../../context/ToastContext';
import { Card } from '../../components/ui/Card';
import { Field, Input } from '../../components/ui/Field';
import Button from '../../components/ui/Button';

// Identity fields (nombres/apellidos/documento) come from the
// cooperative's roster and are read-only here — the backend's
// AfiliadoSelfUpdate schema only accepts correo/telefono, matching the
// functional spec's "perfil del afiliado" scope (see
// backend/app/schemas/afiliado.py). There is no `ciudad` column on the
// real `afiliados` table, so that field does not exist here.
export default function EditProfile() {
  const { afiliado, updateProfile } = useAffiliateAuth();
  const navigate = useNavigate();
  const { push } = useToast();
  const [form, setForm] = useState({ correo: afiliado.correo, telefono: afiliado.telefono ?? '' });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    const nextErrors = {};
    if (!/^\S+@\S+\.\S+$/.test(form.correo)) nextErrors.correo = 'Ingresa un correo electrónico válido.';
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;

    setSaving(true);
    try {
      await updateProfile(form);
      push({ title: 'Perfil actualizado', description: 'Tus datos de contacto se guardaron correctamente.' });
      navigate('/portal/perfil');
    } catch (err) {
      push({ title: 'No se pudo actualizar el perfil', description: err.message, variant: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="text-h1 page-title">Editar perfil</h1>
          <p className="page-subtitle">Tu nombre y cédula los administra tu cooperativa; aquí puedes actualizar tus datos de contacto.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <Card padding="card-pad-lg" style={{ maxWidth: 480 }}>
          <Field label="Nombre completo">
            <Input value={`${afiliado.nombres} ${afiliado.apellidos}`} disabled />
          </Field>
          <Field label="Documento">
            <Input value={afiliado.documento} disabled />
          </Field>
          <Field label="Correo electrónico" error={errors.correo}>
            <Input type="email" value={form.correo} onChange={set('correo')} />
          </Field>
          <Field label="Teléfono">
            <Input value={form.telefono} onChange={set('telefono')} />
          </Field>

          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <Button type="button" variant="secondary" onClick={() => navigate('/portal/perfil')}>Cancelar</Button>
            <Button type="submit" loading={saving}>Guardar cambios</Button>
          </div>
        </Card>
      </form>
    </div>
  );
}
