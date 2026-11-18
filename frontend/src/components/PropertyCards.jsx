import PropertyCard from './PropertyCard.jsx';

function dedupe(records) {
  const seen = new Set();
  return records.filter((record) => {
    const key = record?.id || record?.record_id;
    if (!key) return true;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export default function PropertyCards({ records = [] }) {
  if (!records.length) return null;
  const items = dedupe(records);

  return (
    <section className="property-section" aria-label="Matching properties">
      <div className="property-section-head">
        <h3 className="property-section-title">Matching properties</h3>
        <span className="property-count">{items.length}</span>
      </div>
      <div className="property-scroller" role="list">
        {items.map((record, index) => (
          <PropertyCard key={record?.id || record?.record_id || index} record={record} />
        ))}
      </div>
    </section>
  );
}
