import React from 'react';

type HeaderProps = {
  showHistory: boolean;
  setShowHistory: (v: boolean) => void;
  setResult: (v: any) => void;
  darkMode: boolean;
  setDarkMode: (v: boolean) => void;
};

export default function Header({ showHistory, setShowHistory, setResult, darkMode, setDarkMode }: HeaderProps) {
  return (
    <header className="border-b border-[var(--border)] bg-[var(--bg-secondary)] sticky top-0 z-10 shadow-sm">
      <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-3xl">🤖</span>
          <div>
            <h1 className="text-xl font-bold tracking-tight">SmartMeet Agent Suite</h1>
            <p className="text-xs text-[var(--text-secondary)]">
              企业级多模态智能会议 · 多 Agent 协同分析
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setShowHistory(!showHistory);
              setResult(null);
            }}
            className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-all font-medium"
          >
            {showHistory ? "返回" : "📋 历史"}
          </button>
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-all"
          >
            {darkMode ? "☀️" : "🌙"}
          </button>
        </div>
      </div>
    </header>
  );
}
