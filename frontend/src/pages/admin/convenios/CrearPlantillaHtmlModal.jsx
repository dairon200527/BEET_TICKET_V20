import { useState } from 'react';
import Modal from '../../../components/ui/Modal';
import Button from '../../../components/ui/Button';
import { Field, Input, Textarea } from '../../../components/ui/Field';
import * as plantillasService from '../../../services/plantillasService';
import { useToast } from '../../../context/ToastContext';

const VARIABLES_REQUERIDAS = '{{ convenio }}, {{ items }}, {{ afiliado }}, {{ transaccion_id }}, {{ fecha_emision }}, {{ fecha_vencimiento }}';

const ESTADO_INICIAL = { nombre: '', html: '' };

// Crea una plantilla REAL para este convenio pegando código HTML/Jinja2
// directamente — sin editor visual, sin posicionamiento manual, sin
// logos ni campos de contenido (todo eso vive dentro del HTML que se
// pega). "Ver muestra" corre exactamente la misma validación y
// renderizado que "Guardar" — nunca puede quedar guardada una plantilla
// que no se pudo previsualizar.
export default function CrearPlantillaHtmlModal({ open, onClose, convenioId, onCreada }) {
  const { push } = useToast();
  const [form, setForm] = useState(ESTADO_INICIAL);
  const [error, setError] = useState(null);
  const [previsualizando, setPrevisualizando] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const set = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }));

  const cerrar = () => {
    setForm(ESTADO_INICIAL);
    setError(null);
    onClose?.();
  };

  const construirFormData = () => {
    const fd = new FormData();
    fd.append('convenio_id', String(convenioId));
    fd.append('html', form.html);
    if (form.nombre) fd.append('nombre', form.nombre);
    return fd;
  };

  const verMuestra = async () => {
    setError(null);
    setPrevisualizando(true);
    try {
      const blob = await plantillasService.previsualizarPlantillaHtml(construirFormData());
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setError(err.message);
    } finally {
      setPrevisualizando(false);
    }
  };

  const guardar = async () => {
    setError(null);
    setGuardando(true);
    try {
      const plantilla = await plantillasService.crearPlantillaHtml(construirFormData());
      push({ title: `Plantilla "${plantilla.nombre}" creada (versión ${plantilla.version})`, variant: 'success' });
      await onCreada?.();
      cerrar();
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Modal open={open} onClose={cerrar} title="Crear plantilla con código HTML" size="lg">
      <p className="text-small cell-muted" style={{ marginBottom: 14 }}>
        Pega el código HTML/Jinja2 del ticket. Debe referenciar las variables: <code>{VARIABLES_REQUERIDAS}</code>.
        Al guardarla queda seleccionada de inmediato para este convenio. Si tiene una plantilla del catálogo
        seleccionada, esa sigue teniendo prioridad — límpiala en "Seleccionar plantilla" para que esta se use al
        generar el ticket.
      </p>

      {error && (
        <div className="text-small" style={{ color: 'var(--error)', background: 'var(--error-soft)', borderRadius: 8, padding: 10, marginBottom: 14, whiteSpace: 'pre-wrap' }}>
          {error}
        </div>
      )}

      <Field label="Nombre de la plantilla" optional hint="Si lo dejas vacío, se usa el nombre del convenio.">
        <Input value={form.nombre} onChange={set('nombre')} placeholder="Diseño oficial" />
      </Field>

      <Field label="Código HTML" hint="HTML/Jinja2 completo — sin editor visual, sin posicionamiento manual.">
        <Textarea
          value={form.html} onChange={set('html')} rows={14}
          style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}
          placeholder={'<html>\n  <body>\n    <h1>{{ convenio.nombre }}</h1>\n    ...\n  </body>\n</html>'}
        />
      </Field>

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
        <Button variant="secondary" onClick={cerrar}>Cancelar</Button>
        <Button variant="ghost" loading={previsualizando} disabled={!form.html} onClick={verMuestra}>Ver muestra</Button>
        <Button variant="primary" loading={guardando} disabled={!form.html} onClick={guardar}>Guardar plantilla</Button>
      </div>
    </Modal>
  );
}
