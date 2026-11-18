import { titleCaseSource } from '../utils/format.js';

function sourceKey(source) {
  const value = String(source || '').toLowerCase();
  if (value === 'darglobal') return 'darglobal';
  if (value === 'wasalt') return 'wasalt';
  return 'unknown';
}

export default function SourceBadge({ source, className = '' }) {
  return (
    <span className={`source-badge ${sourceKey(source)} ${className}`.trim()}>
      {titleCaseSource(source)}
    </span>
  );
}
