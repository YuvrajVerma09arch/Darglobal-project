const LABELS = {
  checking: 'Checking',
  connected: 'Connected',
  limited: 'Limited',
  offline: 'Offline',
};

export default function StatusBadge({ status, onRefresh }) {
  const state = status?.state || 'checking';
  const label = LABELS[state] || LABELS.checking;
  const content = (
    <>
      <span className="status-dot" aria-hidden="true" />
      {label}
    </>
  );
  if (onRefresh) {
    return (
      <button
        type="button"
        className={`status-badge status-${state}`}
        onClick={onRefresh}
        title="Recheck backend connection"
        aria-label={`Backend status: ${label}. Click to recheck.`}
      >
        {content}
      </button>
    );
  }
  return (
    <span className={`status-badge status-${state}`} role="status" aria-label={`Backend status: ${label}`}>
      {content}
    </span>
  );
}
