import { ChevronDown, SlidersHorizontal } from 'lucide-react';

export default function FiltersBar({ sourceFilter, onSourceChange, filters, onFilterChange, isOpen, onToggle }) {
  const setField = (key) => (event) => onFilterChange(key, event.target.value);
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
            placeholder="e.g. Riyadh, Dubai Marina"
            value={filters.location || ''}
            onChange={setField('location')}
          />
        </div>
        <div className="field">
          <label htmlFor="filter-type">Property type</label>
          <select id="filter-type" value={filters.property_type || ''} onChange={setField('property_type')}>
            <option value="">Any type</option>
            <option value="apartment">Apartment</option>
            <option value="villa">Villa</option>
            <option value="townhouse">Townhouse</option>
            <option value="office">Office</option>
            <option value="retail">Retail</option>
            <option value="land">Land</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-bedrooms">Bedrooms</label>
          <select id="filter-bedrooms" value={filters.bedrooms || ''} onChange={setField('bedrooms')}>
            <option value="">Any</option>
            <option value="1">1+</option>
            <option value="2">2+</option>
            <option value="3">3+</option>
            <option value="4">4+</option>
            <option value="5">5+</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-max-price">Max price</label>
          <input
            id="filter-max-price"
            type="number"
            min="0"
            inputMode="numeric"
            placeholder="No limit"
            value={filters.max_price || ''}
            onChange={setField('max_price')}
          />
        </div>
      </div>
    </section>
  );
}
