import { ExternalLink } from 'lucide-react';
import SourceBadge from './SourceBadge.jsx';
import { formatArea, formatPrice, titleCaseSource } from '../utils/format.js';

function citationMeta(item) {
  const parts = [];
  if (item.location) parts.push(item.location);
  const price = formatPrice(item.price, item.currency);
  if (price) parts.push(price);
  const area = formatArea(item.area, item.area_unit);
  if (area) parts.push(area);
  if (item.bedrooms) parts.push(`${item.bedrooms} bed`);
  return parts.join('  ·  ');
}

export default function Citations({ citations = [], messageId }) {
  if (!citations.length) {
    return (
      <p className="citations-empty">
        No matching listings in this snapshot — try a broader location or clear filters.
      </p>
    );
  }

  return (
    <section className="citations" aria-label="Sources used for this answer">
      <h3 className="citations-label">Sources</h3>
      <ol className="citation-list">
        {citations.map((item, index) => {
          const url = item.url || item.source_url;
          const meta = citationMeta(item);
          return (
            <li
              key={item.record_id || item.id || index}
              id={`${messageId}-citation-${index + 1}`}
              className="citation-row"
            >
              <span className="citation-number" aria-hidden="true">{index + 1}</span>
              <SourceBadge source={item.source} />
              <div className="citation-main">
                <span className="citation-title">{item.title || 'Untitled property'}</span>
                {meta && <span className="citation-meta">{meta}</span>}
                {item.snippet && <span className="citation-snippet">{item.snippet}</span>}
              </div>
              {url ? (
                <a
                  className="citation-link"
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`Open source: ${titleCaseSource(item.source)} — ${item.title || 'property'}`}
                  title="Open source"
                >
                  <ExternalLink size={14} aria-hidden="true" />
                </a>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
