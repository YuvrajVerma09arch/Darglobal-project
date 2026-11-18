import { Plus, X } from 'lucide-react';
import { EXAMPLE_QUESTIONS } from '../constants.js';
import { formatDate } from '../utils/format.js';

const SOURCES = [
  { value: 'both', label: 'Both' },
  { value: 'darglobal', label: 'DarGlobal' },
  { value: 'wasalt', label: 'Wasalt' },
];

export default function Sidebar({ sourceFilter, onSourceChange, onNewChat, onExample, dataAsOf, isOpen, onClose }) {
  return (
    <>
      {isOpen ? <div className="sidebar-overlay" onClick={onClose} aria-hidden="true" /> : null}
      <aside className={`sidebar ${isOpen ? 'is-open' : ''}`} aria-label="Assistant navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">D<span>×</span>W</span>
          <span className="brand-copy">
            <span className="brand-name">DarGlobal <span aria-hidden="true">×</span> Wasalt</span>
            <span className="brand-sub">Real Estate Intelligence Assistant</span>
          </span>
          <button type="button" className="icon-btn sidebar-close" onClick={onClose} aria-label="Close menu">
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        <div className="sidebar-body">
          <div className="sidebar-section">
            <button type="button" className="new-chat-btn" onClick={onNewChat}>
              <Plus size={15} aria-hidden="true" />
              New conversation
            </button>
          </div>

          <div className="sidebar-section">
            <p className="sidebar-label" id="source-filter-label">Search sources</p>
            <div className="chip-row" role="group" aria-labelledby="source-filter-label">
              {SOURCES.map((source) => (
                <button
                  key={source.value}
                  type="button"
                  className={`chip ${sourceFilter === source.value ? 'active' : ''}`}
                  aria-pressed={sourceFilter === source.value}
                  onClick={() => onSourceChange(source.value)}
                >
                  {source.label}
                </button>
              ))}
            </div>
          </div>

          <div className="sidebar-section sidebar-examples">
            <p className="sidebar-label" id="example-label">Try asking</p>
            <ul className="example-list" aria-labelledby="example-label">
              {EXAMPLE_QUESTIONS.map((example) => (
                <li key={example.label}>
                  <button type="button" className="example-link" onClick={() => onExample(example.question)}>
                    <span className="example-dot" aria-hidden="true" />
                    <span>{example.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="sidebar-footer">
          <span className="sidebar-footer-label">Data as of</span>
          <span className="sidebar-footer-value">{formatDate(dataAsOf) || 'Snapshot not available'}</span>
          <span className="sidebar-footer-note">Source records only · no generated listings</span>
        </div>
      </aside>
    </>
  );
}
