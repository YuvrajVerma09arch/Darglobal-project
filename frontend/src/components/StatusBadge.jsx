const LABELS = {
  checking: 'Checking',
  connected: 'Connected',
  limited: 'Limited',
  offline: 'Offline',
};

export default function StatusBadge({ status }) {
  const state = status?.state || 'checking';
  const label = LABELS[state] || LABELS.checking;
  return (
    <span className={`status-badge status-${state}`} role="status" aria-label={`Backend status: ${label}`}>
      <span className="status-dot" aria-hidden="true" />
      {label}
    </span>
  );
}
