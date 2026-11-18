/**
 * Renders plain answer text. `[n]` markers become small superscript links that
 * jump to the matching citation row. No HTML is ever injected.
 */
export default function AnswerText({ text, messageId }) {
  if (!text) return null;
  const anchorFor = (number) => `${messageId}-citation-${number}`;

  const nodes = [];
  const marker = /\[(\d+)\]/g;
  let cursor = 0;
  let match;
  let key = 0;

  while ((match = marker.exec(text)) !== null) {
    if (match.index > cursor) {
      nodes.push(<span key={key++}>{text.slice(cursor, match.index)}</span>);
    }
    const number = Number(match[1]);
    nodes.push(
      <a
        key={key++}
        href={`#${anchorFor(number)}`}
        className="citation-marker"
        aria-label={`Go to source ${number}`}
      >
        {number}
      </a>,
    );
    cursor = match.index + match[0].length;
  }

  if (cursor < text.length) nodes.push(<span key={key++}>{text.slice(cursor)}</span>);

  return <p className="answer-text">{nodes}</p>;
}
