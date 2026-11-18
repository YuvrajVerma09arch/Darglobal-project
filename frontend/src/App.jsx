import { useState } from 'react';
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
