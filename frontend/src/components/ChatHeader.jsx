import { Eraser, Menu } from 'lucide-react';
import StatusBadge from './StatusBadge.jsx';

export default function ChatHeader({ status, hasMessages, onClear, onOpenMenu, onRefreshStatus }) {
  return (
    <header className="chat-header">
      <div className="chat-header-left">
        <button type="button" className="icon-btn mobile-menu-btn" onClick={onOpenMenu} aria-label="Open menu">
          <Menu size={18} aria-hidden="true" />
        </button>
        <div className="chat-header-titles">
          <h2 className="chat-header-title">Real Estate Intelligence</h2>
          <p className="chat-header-subtitle">Grounded answers from DarGlobal and Wasalt listings</p>
        </div>
      </div>
      <div className="chat-header-actions">
        <StatusBadge status={status} onRefresh={onRefreshStatus} />
        <button
          type="button"
          className="clear-btn"
          onClick={onClear}
          disabled={!hasMessages}
          aria-label="Clear conversation"
        >
          <Eraser size={14} aria-hidden="true" />
          <span>Clear chat</span>
        </button>
      </div>
    </header>
  );
}
