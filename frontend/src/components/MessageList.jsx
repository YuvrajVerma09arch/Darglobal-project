import MessageItem from './MessageItem.jsx';
import WelcomeScreen from './WelcomeScreen.jsx';

export default function MessageList({ messages, scrollRef, onScroll, onExample }) {
  return (
    <div
      className="message-scroll"
      ref={scrollRef}
      onScroll={onScroll}
      role="log"
      aria-label="Conversation"
      aria-live="polite"
      aria-relevant="additions text"
    >
      {messages.length === 0 ? (
        <WelcomeScreen onExample={onExample} />
      ) : (
        <div className="message-scroll-inner">
          {messages.map((message) => (
            <MessageItem key={message.id} message={message} />
          ))}
        </div>
      )}
    </div>
  );
}
