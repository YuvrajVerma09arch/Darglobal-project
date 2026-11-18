import { useEffect, useRef, useState } from 'react';
import MessageItem from './MessageItem.jsx';
import WelcomeScreen from './WelcomeScreen.jsx';

export default function MessageList({ messages, scrollRef, onScroll, onExample, isStreaming, dataAsOf, onRetry }) {
  const wasStreaming = useRef(false);
  const [readyAnnouncement, setReadyAnnouncement] = useState('');

  useEffect(() => {
    if (isStreaming) {
      wasStreaming.current = true;
      setReadyAnnouncement('');
    } else if (wasStreaming.current) {
      wasStreaming.current = false;
      setReadyAnnouncement('Answer ready');
    }
  }, [isStreaming]);

  return (
    <>
      <span className="sr-only" role="status">{readyAnnouncement}</span>
      <div
        className="message-scroll"
        ref={scrollRef}
        onScroll={onScroll}
        role="log"
        aria-label="Conversation"
        aria-live="polite"
        aria-busy={isStreaming}
      >
        {messages.length === 0 ? (
          <WelcomeScreen onExample={onExample} />
        ) : (
          <div className="message-scroll-inner">
            {messages.map((message) => (
              <MessageItem key={message.id} message={message} dataAsOf={dataAsOf} onRetry={onRetry} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
