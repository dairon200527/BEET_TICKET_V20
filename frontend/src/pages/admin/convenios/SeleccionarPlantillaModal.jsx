import { useEffect, useState } from 'react';
import Modal, { ConfirmDialog } from '../../../components/ui/Modal';
import Button from '../../../components/ui/Button';
import { Badge } from '../../../components/ui/Badge';
import * as plantillasService from '../../../services/plantillasService';
import * as convenioService from '../../../services/convenioService';
import { useToast } from '../../../context/ToastContext';

// The unified list for one convenio: the 4 fixed catalog designs (see
// backend/app/services/plantillas_catalogo.py) PLUS every real
// plantilla created for it with "Crear plantilla con HTML" — a single
// list, a single "en_uso" (in effect) at a time, either kind.
// Selecting one deactivates every other option for this convenio;
// "Dejar de usar" clears the active one without picking a replacement,
// so the convenio goes back to "Sin plantilla seleccionada".
export default function SeleccionarPlantillaModal({ open, onClose, convenioId, onCambio }) {
  const { push } = useToast();
  const [items, setItems] = useState(undefined); // undefined = loading, [] = none
  const [error, setError] = useState(null);
  const [accionEnCurso, setAccionEnCurso] = useState(null); // `${tipo}-${clave|id}`
  const [cargandoPreview, setCargandoPreview] = useState(null);
  const [eliminarTarget, setEliminarTarget] = useState(null);
  const [eliminando, setEliminando] = useState(false);

  const claveDe = (item) => (item.tipo === 'catalogo' ? item.clave : item.id);

  const cargar = () => {
    if (!convenioId) return;
    setError(null);
    plantillasService
      .listarPlantillasDisponibles(convenioId)
      .then(setItems)
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    if (!open) return;
    setItems(undefined);
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, convenioId]);

  const verMuestra = async (item) => {
    setCargandoPreview(claveDe(item));
    try {
      const blob = item.tipo === 'catalogo'
        ? await plantillasService.previsualizarCatalogoPlantilla(item.clave)
        : await plantillasService.previsualizarPlantillaPorId(item.id);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      push({ title: 'No se pudo generar la muestra', description: err.message, variant: 'error' });
    } finally {
      setCargandoPreview(null);
    }
  };

  const seleccionar = async (item) => {
    setAccionEnCurso(claveDe(item));
    try {
      if (item.tipo === 'catalogo') {
        await convenioService.actualizarConvenio(convenioId, { plantilla_catalogo_clave: item.clave });
      } else {
        await plantillasService.actualizarEstadoPlantilla(item.id, true);
      }
      push({ title: `Plantilla "${item.nombre}" seleccionada`, variant: 'success' });
      cargar();
      await onCambio?.();
    } catch (err) {
      push({ title: 'No se pudo guardar la selección', description: err.message, variant: 'error' });
    } finally {
      setAccionEnCurso(null);
    }
  };

  const dejarDeUsar = async (item) => {
    setAccionEnCurso(claveDe(item));
    try {
      if (item.tipo === 'catalogo') {
        await convenioService.actualizarConvenio(convenioId, { plantilla_catalogo_clave: null });
      } else {
        await plantillasService.actualizarEstadoPlantilla(item.id, false);
      }
      push({ title: `Se dejó de usar "${item.nombre}"`, variant: 'success' });
      cargar();
      await onCambio?.();
    } catch (err) {
      push({ title: 'No se pudo actualizar la plantilla', description: err.message, variant: 'error' });
    } finally {
      setAccionEnCurso(null);
    }
  };

  const confirmarEliminar = async () => {
    if (!eliminarTarget) return;
    setEliminando(true);
    try {
      await plantillasService.eliminarPlantilla(eliminarTarget.id);
      setItems((prev) => prev?.filter((i) => !(i.tipo === 'personalizada' && i.id === eliminarTarget.id)) ?? prev);
      push({ title: `Plantilla "${eliminarTarget.nombre}" eliminada`, variant: 'success' });
      setEliminarTarget(null);
      await onCambio?.();
    } catch (err) {
      push({ title: 'No se pudo eliminar la plantilla', description: err.message, variant: 'error' });
    } finally {
      setEliminando(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Seleccionar plantilla" size="lg">
      {error && <div className="text-small" style={{ color: 'var(--error)', marginBottom: 12 }}>{error}</div>}
      {items === undefined && !error && <div className="text-small cell-muted">Cargando plantillas disponibles…</div>}
      {items && items.length === 0 && <div className="text-small cell-muted">No hay plantillas disponibles.</div>}
      {items && items.length > 0 && (
        <div className="grid grid-2" style={{ gap: 12 }}>
          {items.map((item) => {
            const key = claveDe(item);
            return (
              <div key={`${item.tipo}-${key}`} style={{ border: '1px solid var(--border-default)', borderRadius: 10, padding: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{item.nombre}</span>
                  {item.en_uso && <Badge tone="green" dot>En uso</Badge>}
                </div>
                <div className="text-small cell-muted">
                  {item.tipo === 'catalogo' ? 'Diseño oficial' : `Personalizada · versión ${item.version}`}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
                  <Button size="sm" variant="ghost" loading={cargandoPreview === key} onClick={() => verMuestra(item)}>
                    Ver muestra
                  </Button>
                  {item.en_uso ? (
                    <Button size="sm" variant="secondary" loading={accionEnCurso === key} onClick={() => dejarDeUsar(item)}>
                      Dejar de usar
                    </Button>
                  ) : (
                    <Button size="sm" variant="primary" loading={accionEnCurso === key} onClick={() => seleccionar(item)}>
                      Seleccionar
                    </Button>
                  )}
                  {item.tipo === 'personalizada' && (
                    <Button size="sm" variant="ghost" style={{ color: 'var(--error)', marginLeft: 'auto' }} onClick={() => setEliminarTarget(item)}>
                      Eliminar
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <ConfirmDialog
        open={!!eliminarTarget}
        onClose={() => setEliminarTarget(null)}
        title={eliminarTarget ? `¿Eliminar "${eliminarTarget.nombre}"?` : ''}
        description="Esta acción borra la plantilla de forma permanente y no se puede deshacer. Si el convenio la tiene en uso, quedará sin plantilla seleccionada."
        confirmLabel="Eliminar plantilla"
        onConfirm={confirmarEliminar}
        loading={eliminando}
      />
    </Modal>
  );
}
