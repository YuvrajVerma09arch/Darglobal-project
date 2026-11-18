import { AlertCircle, Info, RotateCcw } from 'lucide-react';
import AnswerText from './AnswerText.jsx';
import Citations from './Citations.jsx';
import PropertyCards from './PropertyCards.jsx';
import TypingIndicator from './TypingIndicator.jsx';
import { formatDate } from '../utils/format.js';

const WARNING_COPY = [
  {
    match: /^llm_not_configured$/i,
    text: 'Answer generation is unavailable right now. The matching sources are still shown below.',
  },
  { match: /^no_retrieved_evidence$/i, text: 'No matching evidence in this snapshot.' },
  {
    match: /^filters_relaxed$/i,
    text: 'Your exact filters had no match — these are other real records from the same source.',
  },
  { match: /^llm_unavailable$/i, text: 'The assistant is temporarily unavailable — please retry.' },
  {
    match: /^removed_/i,
    text: 'Some citations were withheld because they could not be verified.',
  },
];
const WARNING_FALLBACK = 'Some information could not be verified and was left out.';

/** Map backend warning codes to short, human copy — never echo raw server strings. */
function friendlyWarning(warning) {
  const code = typeof warning === 'string' ? warning : warning?.code || warning?.reason || '';
  const found = WARNING_COPY.find(({ match }) => match.test(String(code)));
  return found ? found.text : WARNING_FALLBACK;
}

function WarningNotice({ warnings = [] }) {
  const notes = [...new Set(warnings.map(friendlyWarning))];
  if (!notes.length) return null;
  return (
    <div className="answer-warning" role="note">
      <Info size={13} aria-hidden="true" />
      <span>{notes.join(' ')}</span>
    </div>
  );
}

export default function MessageItem({ message, dataAsOf, onRetry }) {
  if (message.role === 'user') {
    return (
      <div className="message-row user">
        <div className="user-bubble">{message.text}</div>
      </div>
    );
  }

  const snapshotDate = message.dataAsOf || dataAsOf;

  return (
    <div className="message-row assistant">
      <div className="assistant-avatar" aria-hidden="true">W</div>
      <div className="assistant-body">
        {message.text ? <AnswerText text={message.text} messageId={message.id} /> : null}
        {message.streaming && !message.text ? <TypingIndicator /> : null}
        {message.streaming && message.text ? <span className="stream-caret" aria-hidden="true" /> : null}
        {snapshotDate ? (
          <p className="citations-label data-currency">Snapshot data · {formatDate(snapshotDate)}</p>
        ) : null}
        {!message.streaming && message.warnings?.length ? (
          <WarningNotice warnings={message.warnings} />
        ) : null}
        {message.error ? (
          <p className="message-error">
            <AlertCircle size={13} aria-hidden="true" /> {message.error}
          </p>
        ) : null}
        {message.stopped ? (
          <div className="message-stopped-row">
            <span className="message-stopped">Answer stopped.</span>
            {onRetry ? (
              <button type="button" className="continue-btn" onClick={onRetry}>
                <RotateCcw size={12} aria-hidden="true" />
                Continue
              </button>
            ) : null}
          </div>
        ) : null}
        {!message.streaming && !message.error && message.text ? (
          <>
            <Citations citations={message.citations} messageId={message.id} />
            <PropertyCards records={message.records} />
          </>
        ) : null}
      </div>
    </div>
  );
}
