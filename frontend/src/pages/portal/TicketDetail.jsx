import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from '../../components/ui/States';
import { Card } from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import TicketCard from '../../components/portal/TicketCard';
import * as ticketsService from '../../services/ticketsService';
import * as convenioService from '../../services/convenioService';
import { useToast } from '../../context/ToastContext';

export default function TicketDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { push } = useToast();

  const [ticket, setTicket] = useState(undefined); // undefined = loading, null = not found/not yours
  const [convenio, setConvenio] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([ticketsService.misTickets(), convenioService.obtenerCatalogoAfiliado()])
      .then(([tickets, convenios]) => {
        const found = tickets.find((t) => String(t.id) === id) ?? null;
        setTicket(found);
        if (found) setConvenio(convenios.find((c) => c.id === found.convenio_id) ?? null);
      })
      .catch((err) => setError(err.message));
  }, [id]);

  const descargar = async () => {
    try {
      // The backend serves raw PDF bytes directly, not a JSON envelope
      // with a URL — turn the Blob into a same-tab object URL the browser
      // can open/download, then release it once the tab has it loaded.
      const blob = await ticketsService.descargarMiTicket(ticket.id);
      const objectUrl = URL.createObjectURL(blob);
      window.open(objectUrl, '_blank', 'noopener,noreferrer');
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (err) {
      push({ title: 'No se pudo descargar el ticket', description: err.message, variant: 'error' });
    }
  };

  if (error) return <ErrorState description={error} onRetry={() => window.location.reload()} />;
  if (ticket === undefined) return <LoadingState title="Cargando ticket…" />;
  if (!ticket) {
    return <EmptyState title="Ticket no encontrado" description="Puede que ya no esté disponible." actionLabel="Volver a Mis tickets" onAction={() => navigate('/portal/tickets')} />;
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <button onClick={() => navigate('/portal/tickets')} className="text-small" style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'var(--brand-primary)', fontWeight: 600 }}>
          ← Mis tickets
        </button>
      </div>

      <div className="grid detail-grid-2col" style={{ '--col-ratio': '1fr 1fr', gap: 20 }}>
        <TicketCard ticket={ticket} convenio={convenio} linkToDetail={false} />

        <Card padding="card-pad-lg">
          <div className="text-label" style={{ marginBottom: 14 }}>Detalle del beneficio</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
            <Row label="Convenio" value={convenio?.nombre} />
            <Row label="Descripción" value={convenio?.descripcion} />
          </div>
          <Button variant="secondary" onClick={descargar}>Descargar</Button>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div>
      <div className="text-label">{label}</div>
      <div style={{ fontSize: 14 }}>{value ?? '—'}</div>
    </div>
  );
}
