"use client";

import { useState, useEffect } from "react";
import { Result, HistoryItem } from "../types";
import Header from "../components/Header";
import HistoryPanel from "../components/HistoryPanel";
import UploadPanel from "../components/UploadPanel";
import ResultPanel from "../components/ResultPanel";

const API_BASE =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://api:8000";

const HISTORY_KEY = "smartmeet_history";
const MAX_HISTORY = 50;

function loadHistory(): HistoryItem[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(items: HistoryItem[]) {
  localStorage.setItem(
    HISTORY_KEY,
    JSON.stringify(items.slice(0, MAX_HISTORY))
  );
}

export default function Home() {
  const [result, setResult] = useState<Result | null>(null);
  
  // UI state
  const [darkMode, setDarkMode] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  const handleUploadSuccess = (r: Result, input: string) => {
    setResult(r);
    const items = loadHistory();
    items.unshift({
      ...r,
      id: Date.now().toString(36),
      input: input,
      timestamp: Date.now(),
      contentPreview: r.content.slice(0, 120).replace(/\n/g, " "),
    });
    saveHistory(items);
    setHistory(loadHistory());
  };

  const handleDeleteHistory = (id: string) => {
    const updated = history.filter((h) => h.id !== id);
    saveHistory(updated);
    setHistory(updated);
  };

  const handleClearHistory = () => {
    saveHistory([]);
    setHistory([]);
  };

  return (
    <div className={darkMode ? "dark" : ""}>
      <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] transition-colors duration-300">
        
        <Header 
          showHistory={showHistory} 
          setShowHistory={setShowHistory} 
          setResult={setResult} 
          darkMode={darkMode} 
          setDarkMode={setDarkMode} 
        />

        <main className="max-w-5xl mx-auto px-4 py-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
          {showHistory ? (
            <HistoryPanel 
              history={history} 
              handleClearHistory={handleClearHistory} 
              handleDeleteHistory={handleDeleteHistory} 
              setResult={setResult} 
              setShowHistory={setShowHistory} 
            />
          ) : !result ? (
            <UploadPanel 
              API_BASE={API_BASE} 
              onSuccess={handleUploadSuccess} 
            />
          ) : (
            <ResultPanel 
              result={result} 
              setResult={setResult} 
              API_BASE={API_BASE} 
            />
          )}
        </main>

        {/* ── Footer ── */}
        <footer className="border-t border-[var(--border)] mt-16">
          <div className="max-w-5xl mx-auto px-4 py-6 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-sm text-[var(--text-secondary)]">
              SmartMeet Agent Suite — 企业级多模态智能会议与全链路协同 Agent 解决方案
            </div>
            <a
              href="https://github.com/drfgjko/smartmeet-agent-suite"
              target="_blank"
              className="text-[var(--accent)] hover:underline flex items-center gap-1 text-sm"
            >
              <svg
                className="w-4 h-4"
                viewBox="0 0 16 16"
                fill="currentColor"
              >
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
              </svg>
              GitHub
            </a>
          </div>
        </footer>
      </div>
    </div>
  );
}
