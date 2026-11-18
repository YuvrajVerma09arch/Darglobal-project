import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchHealth, streamChat } from '../api.js';

let counter = 0;
const uid = () => `msg-${Date.now()}-${counter++}`;
const EMPTY_FILTERS = { location: '', property_type: '', bedrooms: '', max_price: '' };

const RATE_LIMIT_MESSAGE = 'Too many requests — wait a moment, then retry.';
const isRateLimit = (error, detail) =>
  error?.status === 429 || /\b429\b|too many requests/i.test(String(detail || ''));

/** Owns all conversation state, streaming, health and scroll behaviour. */
export default function useChat() {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [errorDetail, setErrorDetail] = useState(null);
  const [sourceFilter, setSourceFilter] = useState('both');
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [status, setStatus] = useState({ state: 'checking' });
  const [dataAsOf, setDataAsOf] = useState(null);

  const abortRef = useRef(null);
  const scrollRef = useRef(null);
  const pinnedRef = useRef(true);

  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal)
      .then((data) => {
        const healthy = data?.status === 'ok';
        const databaseReady = !data?.database || data.database === 'connected';
        setStatus({ state: healthy && databaseReady ? 'connected' : 'limited' });
        if (data?.last_ingest_at) setDataAsOf(data.last_ingest_at);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setStatus({ state: 'offline' });
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!pinnedRef.current || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
  }, []);

  const runStream = useCallback(
    async (text) => {
      const assistantId = uid();
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: 'assistant', text: '', citations: [], records: [], streaming: true },
      ]);
      pinnedRef.current = true;
      setIsStreaming(true);
      setError(null);
      setErrorDetail(null);

      const controller = new AbortController();
      abortRef.current = controller;

      const appendToken = (token) => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId ? { ...message, text: message.text + token } : message,
          ),
        );
      };

      const applyDone = (data) => {
        const messageDataAsOf = data?.data_as_of || data?.dataAsOf || null;
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  text: typeof data?.answer === 'string' ? data.answer : message.text,
                  citations: Array.isArray(data?.citations) ? data.citations : [],
                  records: Array.isArray(data?.records) ? data.records : [],
                  warnings: Array.isArray(data?.warnings) ? data.warnings : [],
                  dataAsOf: messageDataAsOf,
                  streaming: false,
                }
              : message,
          ),
        );
        if (data?.conversation_id) setConversationId(data.conversation_id);
        if (messageDataAsOf) setDataAsOf(messageDataAsOf);
      };

      try {
        await streamChat(
          { message: text, conversationId, sourceFilter, filters, signal: controller.signal },
          { onToken: appendToken, onDone: applyDone },
        );
      } catch (err) {
        if (err.name === 'AbortError') {
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId ? { ...message, streaming: false, stopped: true } : message,
            ),
          );
        } else {
          const detail = err.message || 'The assistant could not complete the request.';
          const friendly = isRateLimit(err, detail) ? RATE_LIMIT_MESSAGE : detail;
          console.error('Chat request failed:', detail);
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantId ? { ...message, streaming: false, error: friendly } : message,
            ),
          );
          setError(friendly);
          setErrorDetail(detail);
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setIsStreaming(false);
      }
    },
    [conversationId, sourceFilter, filters],
  );

  const handleSend = useCallback(
    (raw) => {
      // Ignore non-string arguments (e.g. a stray click event); use current input.
      const candidate = typeof raw === 'string' ? raw : input;
      const text = typeof candidate === 'string' ? candidate.trim() : '';
      if (!text || isStreaming) return;
      setMessages((prev) => [...prev, { id: uid(), role: 'user', text }]);
      setInput('');
      runStream(text);
    },
    [input, isStreaming, runStream],
  );

  const handleRetry = useCallback(() => {
    if (isStreaming) return;
    const lastUser = [...messages].reverse().find((message) => message.role === 'user');
    if (!lastUser) return;
    setMessages((prev) => {
      const next = [...prev];
      while (next.length && next[next.length - 1].role === 'assistant') next.pop();
      return next;
    });
    setError(null);
    setErrorDetail(null);
    runStream(lastUser.text);
  }, [isStreaming, messages, runStream]);

  const handleStop = useCallback(() => abortRef.current?.abort(), []);

  const handleClear = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(null);
    setInput('');
    setError(null);
    setErrorDetail(null);
    pinnedRef.current = true;
  }, []);

  const handleFilterChange = useCallback((key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  return {
    messages,
    input,
    setInput,
    isStreaming,
    error,
    errorDetail,
    setError,
    sourceFilter,
    setSourceFilter,
    filters,
    handleFilterChange,
    status,
    dataAsOf,
    scrollRef,
    handleScroll,
    handleSend,
    handleRetry,
    handleStop,
    handleClear,
  };
}
