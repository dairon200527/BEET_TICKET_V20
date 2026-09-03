import { Link } from 'react-router-dom';

export function Breadcrumbs({ items }) {
  return (
    <div className="breadcrumbs">
      {items.map((item, i) => {
        const last = i === items.length - 1;
        return (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {last || !item.to ? (
              <span className={last ? 'current' : ''}>{item.label}</span>
            ) : (
              <Link to={item.to}>{item.label}</Link>
            )}
            {!last && <span>/</span>}
          </span>
        );
      })}
    </div>
  );
}

export function Tabs({ items, active, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.key}
          role="tab"
          aria-selected={active === item.key}
          className={`tab ${active === item.key ? 'active' : ''}`}
          onClick={() => onChange(item.key)}
        >
          {item.label} {item.count != null && <span className="tab-count">{item.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Pagination({ page, totalPages, onChange, totalLabel }) {
  const pages = [];
  const push = (p) => pages.push(p);
  if (totalPages <= 6) {
    for (let i = 1; i <= totalPages; i++) push(i);
  } else {
    push(1);
    if (page > 3) push('…');
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) push(i);
    if (page < totalPages - 2) push('…');
    push(totalPages);
  }
  return (
    <div className="table-pagination">
      <span className="text-small">{totalLabel}</span>
      <div className="pagination-controls">
        <button className="pagination-btn" disabled={page <= 1} onClick={() => onChange(page - 1)}>‹</button>
        {pages.map((p, i) =>
          p === '…' ? (
            <span key={`e${i}`} className="pagination-ellipsis">…</span>
          ) : (
            <button key={p} className={`pagination-btn ${p === page ? 'active' : ''}`} onClick={() => onChange(p)}>{p}</button>
          )
        )}
        <button className="pagination-btn" disabled={page >= totalPages} onClick={() => onChange(page + 1)}>›</button>
      </div>
    </div>
  );
}

export function Dropdown({ open, onClose, items, style }) {
  if (!open) return null;
  return (
    <>
      <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={onClose} />
      <div className="dropdown-menu" style={{ position: 'absolute', zIndex: 41, ...style }}>
        {items.map((item, i) =>
          item.divider ? (
            <div className="dropdown-divider" key={i} />
          ) : (
            <button
              key={item.label}
              className={`dropdown-item ${item.danger ? 'danger' : ''}`}
              onClick={() => { item.onClick?.(); onClose(); }}
              disabled={item.disabled}
              style={item.disabled ? { color: 'var(--text-disabled)', cursor: 'not-allowed' } : undefined}
            >
              {item.label}
            </button>
          )
        )}
      </div>
    </>
  );
}
