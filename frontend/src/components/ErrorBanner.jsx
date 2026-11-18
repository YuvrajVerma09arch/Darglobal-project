import { AlertCircle, RotateCcw, X } from 'lucide-react';

export default function ErrorBanner({ message, detail, onRetry, onDismiss }) {
  if (!message) return null;
  return (
    <div className="error-banner" role="alert">
      <AlertCircle size={16} aria-hidden="true" />
      <span className="error-banner-text" title={detail || undefined}>{message}</span>
      {onRetry && (
        <button type="button" className="error-retry" onClick={onRetry}>
          <RotateCcw size={13} aria-hidden="true" />
          Retry
        </button>
      )}
      {onDismiss && (
        <button type="button" className="icon-btn error-dismiss" onClick={onDismiss} aria-label="Dismiss error">
          <X size={15} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
