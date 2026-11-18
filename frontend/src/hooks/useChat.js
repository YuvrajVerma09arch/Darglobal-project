import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchHealth, streamChat } from '../api.js';

let counter = 0;
const uid = () => `msg-${Date.now()}-${counter++}`;
const EMPTY_FILTERS = { location: '', property_type: '', bedrooms: '', max_price: '' };
const HISTORY_KEY = 're_ai_conversations';

function loadSavedConversations() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.slice(0, 20) : [];
  } catch {
    return [];
  }
}

const RATE_LIMIT_MESSAGE = 'Too many requests — wait a moment, then retry.';
const isRateLimit = (error, detail) =>
  error?.status === 429 || /\b429\b|too many requests/i.test(String(detail || ''));

/** Owns all conversation state, streaming, health and scroll behaviour. */
export default function useChat() {
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [savedConversations, setSavedConversations] = useState(loadSavedConversations);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [errorDetail, setErrorDetail] = useState(null);
  const [sourceFilter, setSourceFilter] = useState('both');
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [status, setStatus] = useState({ state: 'checking' });
  const [dataAsOf, setDataAsOf] = useState(null);

  const abortRef = useRef(null);
  const persistTimer = useRef(null);
  const scrollRef = useRef(null);
  const pinnedRef = useRef(true);

  const checkHealth = useCallback(async (signal) => {
    setStatus({ state: 'checking' });
    try {
      const data = await fetchHealth(signal);
      const healthy = data?.status === 'ok';
      const databaseReady = !data?.database || data.database === 'connected';
      setStatus({ state: healthy && databaseReady ? 'connected' : 'limited' });
      if (data?.last_ingest_at) setDataAsOf(data.last_ingest_at);
    } catch (err) {
      if (err.name !== 'AbortError') setStatus({ state: 'offline' });
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    checkHealth(controller.signal);
    return () => controller.abort();
  }, [checkHealth]);

  useEffect(() => {
    if (!pinnedRef.current || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  // Keep a local archive of conversations so "New conversation" never destroys
  // previous chats. Only chat text is stored here — no credentials or tokens.
  useEffect(() => {
    if (!messages.length || !conversationId) return undefined;
    clearTimeout(persistTimer.current);
    persistTimer.current = setTimeout(() => {
      const title = messages.find((m) => m.role === 'user')?.text?.slice(0, 60) || 'Conversation';
      setSavedConversations((previous) => {
        const entry = { id: conversationId, title, messages, updatedAt: Date.now() };
        const next = [entry, ...previous.filter((c) => c.id !== conversationId)].slice(0, 20);
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); } catch { /* storage disabled */ }
        return next;
      });
    }, 400);
    return () => clearTimeout(persistTimer.current);
  }, [messages, conversationId]);

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

  // Both "New conversation" and "Clear chat" archive the current chat, then
  // start a blank one. Nothing is deleted from the recent list.
  const handleClear = useCallback(() => {
    abortRef.current?.abort();
    if (messages.length && conversationId) {
      const title = messages.find((m) => m.role === 'user')?.text?.slice(0, 60) || 'Conversation';
      const entry = { id: conversationId, title, messages, updatedAt: Date.now() };
      setSavedConversations((previous) => {
        const next = [entry, ...previous.filter((c) => c.id !== conversationId)].slice(0, 20);
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); } catch { /* storage disabled */ }
        return next;
      });
    }
    setMessages([]);
    setConversationId(null);
    setInput('');
    setError(null);
    setErrorDetail(null);
    pinnedRef.current = true;
  }, [messages, conversationId]);

  const handleSelectConversation = useCallback((id) => {
    const entry = savedConversations.find((c) => c.id === id);
    if (!entry) return;
    abortRef.current?.abort();
    setMessages(Array.isArray(entry.messages) ? entry.messages : []);
    setConversationId(entry.id);
    setInput('');
    setError(null);
    setErrorDetail(null);
    pinnedRef.current = true;
  }, [savedConversations]);

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
    checkHealth,
    dataAsOf,
    scrollRef,
    handleScroll,
    handleSend,
    handleRetry,
    handleStop,
    handleClear,
    savedConversations,
    handleSelectConversation,
  };
}
