import { useEffect, useState } from 'react';
import { fetchAccessRequirement, unlockWithCode } from './api.js';
import AccessGate from './components/AccessGate.jsx';
import useChat from './hooks/useChat.js';
import ChatHeader from './components/ChatHeader.jsx';
import Composer from './components/Composer.jsx';
import ErrorBanner from './components/ErrorBanner.jsx';
import FiltersBar from './components/FiltersBar.jsx';
import MessageList from './components/MessageList.jsx';
import Sidebar from './components/Sidebar.jsx';

export default function App() {
  const chat = useChat();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [access, setAccess] = useState({ ready: false, required: false, unlocked: false });

  useEffect(() => {
    let alive = true;
    fetchAccessRequirement()
      .then((data) => {
        if (!alive) return;
        const required = Boolean(data?.access_required);
        setAccess({ ready: true, required, unlocked: !required });
      })
      .catch(() => {
        // If the probe fails, let the app load and surface its own error states.
        if (alive) setAccess({ ready: true, required: false, unlocked: true });
      });
    return () => { alive = false; };
  }, []);

  const handleUnlock = async (code) => {
    await unlockWithCode(code);
    setAccess({ ready: true, required: true, unlocked: true });
  };

  if (!access.ready) {
    return <div className="app-loading" role="status">Loading…</div>;
  }
  if (access.required && !access.unlocked) {
    return <AccessGate onUnlock={handleUnlock} />;
  }

  const openExample = (question) => {
    chat.handleSend(question);
    setSidebarOpen(false);
  };

  const clearChat = () => {
    chat.handleClear();
    setSidebarOpen(false);
  };

  return (
    <div className="app-shell">
      <Sidebar
        sourceFilter={chat.sourceFilter}
        onSourceChange={chat.setSourceFilter}
        onNewChat={clearChat}
        onExample={openExample}
        dataAsOf={chat.dataAsOf}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="main-column">
        <ChatHeader
          status={chat.status}
          hasMessages={chat.messages.length > 0}
          onClear={clearChat}
          onOpenMenu={() => setSidebarOpen(true)}
          onRefreshStatus={() => chat.checkHealth()}
        />

        <ErrorBanner
          message={chat.error}
          detail={chat.errorDetail}
          onRetry={chat.handleRetry}
          onDismiss={() => chat.setError(null)}
        />

        <MessageList
          messages={chat.messages}
          scrollRef={chat.scrollRef}
          onScroll={chat.handleScroll}
          onExample={openExample}
          isStreaming={chat.isStreaming}
          dataAsOf={chat.dataAsOf}
          onRetry={chat.handleRetry}
        />

        <div className="composer-area">
          <div className="composer-inner">
            <FiltersBar
              sourceFilter={chat.sourceFilter}
              onSourceChange={chat.setSourceFilter}
              filters={chat.filters}
              onFilterChange={chat.handleFilterChange}
              isOpen={filtersOpen}
              onToggle={() => setFiltersOpen((open) => !open)}
            />
            <Composer
              value={chat.input}
              onChange={chat.setInput}
              onSend={chat.handleSend}
              isStreaming={chat.isStreaming}
              onStop={chat.handleStop}
            />
            <p className="composer-footnote">
              Answers are grounded in indexed listings. Verify availability with the linked source.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
