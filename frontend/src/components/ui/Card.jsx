import { IconTrendUp } from './Icons';

export function Card({ children, brand = false, className = '', padding = 'card-pad', ...rest }) {
  return (
    <div className={`card ${brand ? 'card-brand' : ''} ${padding} ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function KpiCard({ label, value, delta, deltaTone = 'positive', icon }) {
  return (
    <Card className="kpi-card">
      <div className="text-label kpi-label">{label}</div>
      <div className="kpi-value tabular">{value}</div>
      {delta && (
        <div className={`kpi-delta ${deltaTone}`}>
          {deltaTone === 'positive' && <IconTrendUp color="var(--success-text)" />}
          {icon}
          {delta}
        </div>
      )}
    </Card>
  );
}

export function ProgressStatCard({ label, pct, usedLabel, availableLabel, tone = 'green' }) {
  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
        <span className="text-label">{label}</span>
        <span className="text-mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>{pct}%</span>
      </div>
      <div className="progress-track" style={{ marginBottom: 12 }}>
        <div className={`progress-fill ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)' }}>
        <span>{usedLabel}</span>
        <span>{availableLabel}</span>
      </div>
    </Card>
  );
}
