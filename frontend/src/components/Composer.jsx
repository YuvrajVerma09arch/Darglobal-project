import { useEffect, useRef } from 'react';
import { Send, Square } from 'lucide-react';

export default function Composer({ value, onChange, onSend, isStreaming, onStop }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!isStreaming && value.trim()) onSend();
    }
  };

  return (
    <div className="composer-box">
      <label className="sr-only" htmlFor="chat-input">Message the assistant</label>
      <textarea
        id="chat-input"
        ref={textareaRef}
        className="composer-textarea"
        rows={1}
        placeholder="Ask about projects, listings, prices or amenities…"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      {isStreaming ? (
        <button type="button" className="icon-btn stop-btn" onClick={onStop} aria-label="Stop generating">
          <Square size={14} fill="currentColor" aria-hidden="true" />
        </button>
      ) : (
        <button
          type="button"
          className="send-btn"
          onClick={() => onSend()}
          disabled={!value.trim()}
          aria-label="Send message"
        >
          <Send size={15} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
