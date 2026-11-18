import { AlertCircle } from 'lucide-react';
import AnswerText from './AnswerText.jsx';
import Citations from './Citations.jsx';
import PropertyCards from './PropertyCards.jsx';
import TypingIndicator from './TypingIndicator.jsx';

export default function MessageItem({ message }) {
  if (message.role === 'user') {
    return (
      <div className="message-row user">
        <div className="user-bubble">{message.text}</div>
      </div>
    );
  }

  return (
    <div className="message-row assistant">
      <div className="assistant-avatar" aria-hidden="true">W</div>
      <div className="assistant-body">
        {message.text ? <AnswerText text={message.text} /> : null}
        {message.streaming && !message.text ? <TypingIndicator /> : null}
        {message.streaming && message.text ? <span className="stream-caret" aria-hidden="true" /> : null}
        {message.error ? (
          <p className="message-error">
            <AlertCircle size={13} aria-hidden="true" /> {message.error}
          </p>
        ) : null}
        {message.stopped ? <p className="message-stopped">Answer stopped.</p> : null}
        {!message.streaming && !message.error && message.text ? (
          <>
            <Citations citations={message.citations} />
            <PropertyCards records={message.records} />
          </>
        ) : null}
      </div>
    </div>
  );
}
