import { useState } from 'react';
import { Bath, BedDouble, Building2, ExternalLink, Ruler } from 'lucide-react';
import SourceBadge from './SourceBadge.jsx';
import { formatArea, formatPrice } from '../utils/format.js';

export default function PropertyCard({ record }) {
  const [imageFailed, setImageFailed] = useState(false);
  const image = !imageFailed && record?.image_urls?.length ? record.image_urls[0] : null;
  const price = formatPrice(record?.price, record?.currency);
  const area = formatArea(record?.area, record?.area_unit);
  const url = record?.source_url || record?.url;

  const facts = [
    record?.bedrooms ? { icon: BedDouble, text: `${record.bedrooms} bd` } : null,
    record?.bathrooms ? { icon: Bath, text: `${record.bathrooms} ba` } : null,
    area ? { icon: Ruler, text: area } : null,
  ].filter(Boolean);

  return (
    <article className="property-card" role="listitem">
      <div className="property-thumb">
        {image ? (
          <img src={image} alt={record?.title || 'Property'} loading="lazy" onError={() => setImageFailed(true)} />
        ) : (
          <span className="property-thumb-placeholder" aria-hidden="true">
            <Building2 size={26} strokeWidth={1.4} />
          </span>
        )}
      </div>
      <div className="property-card-body">
        <SourceBadge source={record?.source} />
        <h4 className="property-title">{record?.title || 'Untitled property'}</h4>
        {record?.location && <p className="property-location">{record.location}</p>}
        {price && <p className="property-price">{price}</p>}
        {facts.length > 0 && (
          <div className="property-facts">
            {facts.map(({ icon: Icon, text }) => (
              <span key={text} className="property-fact">
                <Icon size={13} aria-hidden="true" />
                {text}
              </span>
            ))}
          </div>
        )}
        {url && (
          <a
            className="property-link"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`View property: ${record?.title || 'listing'}`}
          >
            View listing <ExternalLink size={12} aria-hidden="true" />
          </a>
        )}
      </div>
    </article>
  );
}
