export default function TypingIndicator() {
  return (
    <div className="typing-indicator" role="status" aria-label="The assistant is writing a response">
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-label">Searching sources and composing an answer</span>
    </div>
  );
}
