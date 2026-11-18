/**
 * Thin API client for the DarGlobal × Wasalt backend.
 * Streaming chat uses Server-Sent Events and always consumes the `done` event,
 * which is the authoritative source for citations, records and conversation_id.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

// Shared access code, kept in memory only (never localStorage/sessionStorage).
let accessCode = '';
export const setAccessCode = (code) => { accessCode = code || ''; };
const withAccess = () => (accessCode ? { 'X-Access-Code': accessCode } : {});

/** Public probe: does this deployment require an access code? */
export async function fetchAccessRequirement(signal) {
  const response = await fetch(`${API_BASE}/api/v1/access`, { signal });
  if (!response.ok) throw new Error('Could not read access requirements');
  return response.json();
}

/** Verify a code against a lightweight gated endpoint and remember it in memory. */
export async function unlockWithCode(code) {
  const response = await fetch(`${API_BASE}/api/v1/properties?limit=1`, {
    headers: { 'X-Access-Code': code },
  });
  if (!response.ok) throw new Error('That access code was not accepted.');
  accessCode = code;
}

/** Convert UI filter state into the JSON shape expected by /api/v1/chat. */
export function normalizeFilters(filters = {}) {
  const normalized = {};
  const textFields = ['location', 'city', 'property_type', 'listing_type', 'search'];
  for (const key of textFields) {
    const value = filters[key];
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      normalized[key] = String(value).trim();
    } else {
      normalized[key] = null;
    }
  }
  const numericFields = ['min_price', 'max_price', 'bedrooms', 'bathrooms'];
  for (const key of numericFields) {
    const value = filters[key];
    if (value === undefined || value === null || value === '') {
      normalized[key] = null;
      continue;
    }
    const number = Number(value);
    normalized[key] = Number.isFinite(number) ? number : null;
  }
  return normalized;
}

function extractDetail(payload, fallback) {
  if (typeof payload === 'string') return payload || fallback;
  if (payload && typeof payload.detail === 'string') return payload.detail;
  if (payload && payload.detail) return JSON.stringify(payload.detail);
  return fallback;
}

async function readError(response) {
  const fallback = `Request failed (${response.status})`;
  let error;
  try {
    const payload = await response.json();
    error = new Error(extractDetail(payload, fallback));
  } catch {
    error = new Error(fallback);
  }
  error.status = response.status;
  return error;
}

/**
 * Stream a chat answer.
 *
 * @param {object} request  { message, conversationId, sourceFilter, filters, signal }
 * @param {object} handlers { onToken(text), onDone(response), onError(error) }
 * @returns {Promise<object>} the full ChatResponse from the `done` event
 */
export async function streamChat(request, handlers = {}) {
  const { message, conversationId, sourceFilter, filters, signal } = request;
  const body = {
    message,
    stream: true,
    source_filter: sourceFilter || 'both',
    filters: normalizeFilters(filters),
  };
  if (conversationId) body.conversation_id = conversationId;

  const response = await fetch(`${API_BASE}/api/v1/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...withAccess(),
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) throw await readError(response);

  const contentType = response.headers.get('content-type') || '';

  // Graceful fallback if the server answers with a plain JSON body.
  if (!contentType.includes('text/event-stream')) {
    const data = await response.json();
    if (typeof data?.answer === 'string' && handlers.onToken) {
      handlers.onToken(data.answer);
    }
    if (handlers.onDone) handlers.onDone(data);
    return data;
  }

  if (!response.body) throw new Error('Streaming is not supported by this browser.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResponse = null;
  let streamError = null;

  const handleBlock = (block) => {
    let event = 'message';
    const dataLines = [];
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
    }
    if (dataLines.length === 0) return;

    let payload;
    try {
      payload = JSON.parse(dataLines.join('\n'));
    } catch {
      return; // Ignore malformed/unknown events without breaking the stream.
    }

    if (event === 'token') {
      const text = typeof payload === 'string' ? payload : payload?.text;
      if (text && handlers.onToken) handlers.onToken(text);
    } else if (event === 'done') {
      finalResponse = payload;
      if (handlers.onDone) handlers.onDone(payload);
    } else if (event === 'error') {
      streamError = new Error(extractDetail(payload, 'The assistant could not complete the answer.'));
      if (handlers.onError) handlers.onError(streamError);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, '\n');
      let splitAt;
      while ((splitAt = buffer.indexOf('\n\n')) !== -1) {
        handleBlock(buffer.slice(0, splitAt));
        buffer = buffer.slice(splitAt + 2);
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) handleBlock(buffer);
  } finally {
    reader.releaseLock();
  }

  if (streamError) throw streamError;
  if (!finalResponse) throw new Error('The response stream ended before it was complete.');
  return finalResponse;
}

/** Corpus stats — used to build filter options from real indexed data. */
export async function fetchStats(signal) {
  const response = await fetch(`${API_BASE}/api/v1/stats`, { signal, headers: withAccess() });
  if (!response.ok) throw new Error('Could not load corpus stats');
  return response.json();
}

/** Lightweight backend health probe for the connection badge. */
export async function fetchHealth(signal) {
  const response = await fetch(`${API_BASE}/health`, { signal });
  if (!response.ok) throw new Error(`Health check failed (${response.status})`);
  return response.json();
}
