import { ChevronDown, SlidersHorizontal } from 'lucide-react';

export default function FiltersBar({ sourceFilter, onSourceChange, filters, onFilterChange, stats, isOpen, onToggle }) {
  const setField = (key) => (event) => onFilterChange(key, event.target.value);
  const cities = Object.keys(stats?.cities || {}).sort();
  const types = Object.keys(stats?.property_types || {}).sort();
  const bedrooms = stats?.bedrooms?.length ? stats.bedrooms : [1, 2, 3, 4, 5];
  const maxPriceHint = stats?.max_price ? Math.round(stats.max_price).toLocaleString('en-US') : 'No limit';
  const activeCount =
    Object.values(filters || {}).filter(
      (value) => value !== '' && value !== null && value !== undefined,
    ).length + (sourceFilter && sourceFilter !== 'both' ? 1 : 0);

  return (
    <section className={`filters-bar ${isOpen ? 'is-open' : ''}`} aria-label="Search filters">
      <div className="filters-head">
        <button
          type="button"
          className="filters-toggle"
          onClick={onToggle}
          aria-expanded={isOpen}
          aria-controls="filters-grid"
        >
          <SlidersHorizontal size={14} aria-hidden="true" />
          {!isOpen && activeCount ? `Filters · ${activeCount} active` : 'Filters'}
          <ChevronDown size={14} className="filters-chevron" aria-hidden="true" />
        </button>
        {activeCount ? (
          <button
            type="button"
            className="filters-clear"
            onClick={() => {
              Object.keys(filters || {}).forEach((key) => onFilterChange(key, ''));
              onSourceChange('both');
            }}
            title="Reset all filters"
          >
            Clear filters
          </button>
        ) : null}
      </div>

      <div className="filters-grid" id="filters-grid">
        <div className="field">
          <label htmlFor="filter-source">Source</label>
          <select
            id="filter-source"
            value={sourceFilter}
            onChange={(event) => onSourceChange(event.target.value)}
            aria-label="Source filter — same setting as the source buttons in the menu"
          >
            <option value="both">All sources</option>
            <option value="darglobal">DarGlobal</option>
            <option value="wasalt">Wasalt</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-location">Location</label>
          <input
            id="filter-location"
            type="text"
            placeholder={cities.length ? `e.g. ${cities.slice(0, 2).join(', ')}` : 'e.g. Riyadh'}
            list="filter-location-options"
            value={filters.location || ''}
            onChange={setField('location')}
          />
          <datalist id="filter-location-options">
            {cities.map((city) => <option key={city} value={city} />)}
          </datalist>
        </div>
        <div className="field">
          <label htmlFor="filter-type">Property type</label>
          <select id="filter-type" value={filters.property_type || ''} onChange={setField('property_type')}>
            <option value="">Any type</option>
            {types.map((type) => <option key={type} value={type.toLowerCase()}>{type}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-bedrooms">Bedrooms</label>
          <select id="filter-bedrooms" value={filters.bedrooms || ''} onChange={setField('bedrooms')}>
            <option value="">Any</option>
            {bedrooms.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-max-price">Max price</label>
          <input
            id="filter-max-price"
            type="number"
            min="0"
            inputMode="numeric"
            placeholder={maxPriceHint}
            value={filters.max_price || ''}
            onChange={setField('max_price')}
          />
        </div>
      </div>
    </section>
  );
}
