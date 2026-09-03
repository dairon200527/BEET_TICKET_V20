import { Link } from 'react-router-dom';
import { StatusBadge, Badge } from '../ui/Badge';

// `ticket` is the real TicketOut from GET /api/tickets/me (snake_case,
// canonical inventory states — see backend/app/models/enums.py). Unlike an
// earlier design assumption, `unidades_inventario` has no
// `fecha_vencimiento` column in the real schema, so there is no per-ticket
// expiration to show or warn about here.
export default function TicketCard({ ticket, convenio, linkToDetail = true }) {
  const content = (
    <div className="ticket-card">
      <div className="ticket-card-notch ticket-card-notch-left" />
      <div className="ticket-card-notch ticket-card-notch-right" />
      <div className="ticket-card-header">
        <div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{convenio?.nombre ?? '—'}</div>
        </div>
        <StatusBadge status={ticket.estado} />
      </div>

      <div className="ticket-card-divider" />

      <div className="ticket-card-body">
        <div className="ticket-code-block">
          <div className="ticket-barcode-placeholder" aria-hidden="true">
            {Array.from({ length: 22 }).map((_, i) => (
              <span key={i} style={{ width: i % 3 === 0 ? 2.5 : 1.2 }} />
            ))}
          </div>
          <span className="text-mono ticket-code-text">{ticket.codigo}</span>
        </div>
      </div>

      {linkToDetail && (
        <div className="ticket-card-footer">
          <Badge tone="outline">Ver detalle</Badge>
        </div>
      )}
    </div>
  );

  if (!linkToDetail) return content;
  return <Link to={`/portal/tickets/${ticket.id}`} className="ticket-card-link">{content}</Link>;
}
