import { useEffect, useState } from 'react';
import Modal from '../../../components/ui/Modal';
import Button from '../../../components/ui/Button';
import { Field, Input } from '../../../components/ui/Field';

// NOTE: unlike an earlier design assumption, the real `cupos_credito`
// table has no `periodicidad` column, and `cupo_disponible` stores the
// remaining/available balance DIRECTLY (not an accumulated "used"
// amount) — see backend/app/models/cupo_credito.py.
export default function CupoFormModal({ open, onClose, afiliado, onSave }) {
  const [total, setTotal] = useState(afiliado?.cupo.total ?? 0);

  useEffect(() => {
    if (afiliado) setTotal(afiliado.cupo.total);
  }, [afiliado]);

  if (!afiliado) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Cupo de crédito · ${afiliado.nombres} ${afiliado.apellidos}`}
      actions={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button onClick={() => onSave({ total: Number(total) })}>Guardar cupo</Button>
        </>
      }
    >
      <Field label="Monto del cupo" hint="Cuánto puede consumir el afiliado pagando con cupo de la cooperativa.">
        <Input type="number" min="0" step="10000" value={total} onChange={(e) => setTotal(e.target.value)} />
      </Field>
    </Modal>
  );
}
