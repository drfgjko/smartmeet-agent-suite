import React from 'react';
import { HistoryItem, Result } from '../types';

type HistoryPanelProps = {
  history: HistoryItem[];
  handleClearHistory: () => void;
  handleDeleteHistory: (id: string) => void;
  setResult: (r: Result) => void;
  setShowHistory: (v: boolean) => void;
};

export default function HistoryPanel({ history, handleClearHistory, handleDeleteHistory, setResult, setShowHistory }: HistoryPanelProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold">处理历史</h2>
        {history.length > 0 && (
          <button
            onClick={handleClearHistory}
            className="text-sm text-red-500 hover:underline font-medium"
          >
            清空全部
          </button>
        )}
      </div>
      {history.length === 0 ? (
        <div className="text-center py-20 border border-dashed border-[var(--border)] rounded-2xl">
          <span className="text-4xl mb-3 block">⏳</span>
          <p className="text-[var(--text-secondary)]">暂无历史记录</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {history.map((h) => (
            <div
              key={h.id}
              className="p-5 rounded-2xl border border-[var(--border)] bg-[var(--bg-secondary)] cursor-pointer hover:border-[var(--accent)] hover:shadow-md transition-all group"
              onClick={() => {
                setResult(h);
                setShowHistory(false);
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-base group-hover:text-[var(--accent)] transition-colors">{h.title}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs px-2 py-1 bg-[var(--bg-primary)] rounded-md text-[var(--text-secondary)]">
                    {new Date(h.timestamp).toLocaleString("zh-CN")}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteHistory(h.id);
                    }}
                    className="text-xs text-red-400 hover:text-red-600 font-medium"
                  >
                    删除
                  </button>
                </div>
              </div>
              <p className="text-sm text-[var(--text-secondary)] mb-2 flex items-center gap-2">
                <span>{h.source === "url" ? "🔗 链接" : "📁 文件"}</span>
                <span>•</span>
                <span className="truncate">{h.input}</span>
              </p>
              <p className="text-sm text-[var(--text-secondary)] line-clamp-2 opacity-80">
                {h.contentPreview}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
