import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Result } from '../types';

type ResultPanelProps = {
  result: Result;
  setResult: (v: Result | null) => void;
  API_BASE: string;
};

export default function ResultPanel({ result, setResult, API_BASE }: ResultPanelProps) {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState("report");

  const handleCopy = () => {
    const text = result?.content;
    if (text) {
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownloadMd = () => {
    const content = result?.content;
    if (!content) return;
    const blob = new Blob([content], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${result?.title || "report"}.md`;
    a.click();
  };

  return (
    <div className="animate-in fade-in zoom-in-95 duration-300">
      {/* Header Info */}
      <div className="flex items-start justify-between mb-8 pb-6 border-b border-[var(--border)]">
        <div>
          <h2 className="text-2xl font-extrabold mb-2">{result.title}</h2>
          <div className="flex flex-wrap items-center gap-4 text-sm text-[var(--text-secondary)] font-medium">
            {result.duration > 0 && (
              <span className="flex items-center gap-1">⏱️ {Math.floor(result.duration / 60)}分{Math.floor(result.duration % 60)}秒</span>
            )}
            {result.num_speakers && (
              <span className="flex items-center gap-1">👥 {result.num_speakers} 人</span>
            )}
            {result.speakers && result.speakers.length > 0 && (
              <span className="flex items-center gap-1 bg-[var(--bg-secondary)] px-2 py-0.5 rounded-md">🎙️ {result.speakers.join(", ")}</span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={handleCopy} className="px-4 py-2 text-sm font-semibold rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-all">
            {copied ? "✅" : "📋 复制"}
          </button>
          <button onClick={() => setResult(null)} className="px-4 py-2 text-sm font-semibold rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] hover:border-[var(--text-secondary)] transition-all">
            返回主页
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex overflow-x-auto gap-2 mb-6 hide-scrollbar pb-2">
        {[
          { id: "summary", label: "✨ AI 纪要", show: !!result.summary },
          { id: "actions", label: "✅ 待办事项", show: !!result.actions },
          { id: "insights", label: "📊 洞察分析", show: !!result.insights },
          { id: "transcript", label: "💬 逐字稿", show: !!result.diarized_transcript },
          { id: "report", label: "📄 完整报告", show: true },
        ].map(tab => tab.show && (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`whitespace-nowrap px-5 py-2.5 rounded-xl text-sm font-bold transition-all ${
              activeTab === tab.id
                ? "bg-[var(--accent)] text-white shadow-md"
                : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] border border-[var(--border)] hover:border-[var(--accent)] hover:text-[var(--text-primary)]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6 shadow-sm min-h-[500px]">
        
        {/* ── Summary Tab ── */}
        {activeTab === "summary" && result.summary && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2">
            {result.summary.topics?.map((topic: any, idx: number) => (
              <div key={idx} className="bg-[var(--bg-primary)] p-5 rounded-xl border border-[var(--border)] shadow-sm hover:shadow-md transition-shadow">
                <h3 className="text-lg font-bold mb-3 text-[var(--accent)] flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-xs">{idx + 1}</span>
                  {topic.title}
                </h3>
                <ul className="list-disc list-inside space-y-1 mb-4 text-sm">
                  {topic.discussion_points?.map((pt: string, i: number) => <li key={i}>{pt}</li>)}
                </ul>
                {topic.conclusion && (
                  <div className="p-3 bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300 text-sm rounded-lg border border-green-100 dark:border-green-800/50">
                    <strong>结论：</strong>{topic.conclusion}
                  </div>
                )}
              </div>
            ))}
            {result.summary.decisions?.length > 0 && (
              <div className="p-5 rounded-xl bg-purple-50 dark:bg-purple-900/20 border border-purple-100 dark:border-purple-800/50">
                <h3 className="font-bold text-purple-800 dark:text-purple-300 mb-2">📌 核心决策</h3>
                <ul className="list-disc list-inside text-sm space-y-1 text-purple-900 dark:text-purple-200">
                  {result.summary.decisions.map((d: string, i: number) => <li key={i}>{d}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* ── Actions Tab ── */}
        {activeTab === "actions" && result.actions && (
          <div className="animate-in fade-in slide-in-from-bottom-2">
            {result.actions.action_items?.length === 0 ? (
              <p className="text-center text-[var(--text-secondary)] py-10">未检测到待办事项</p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                {result.actions.action_items?.map((act: any, idx: number) => (
                  <div key={idx} className="bg-[var(--bg-primary)] p-5 rounded-xl border border-[var(--border)] flex flex-col justify-between hover:border-[var(--accent)] transition-colors">
                    <div>
                      <div className="flex justify-between items-start mb-3">
                        <span className="text-xs font-bold px-2 py-1 bg-[var(--bg-secondary)] rounded border border-[var(--border)]">👤 {act.assignee}</span>
                        <span className={`text-xs font-bold px-2 py-1 rounded ${
                          act.priority === 'High' || act.priority === 'urgent' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' :
                          act.priority === 'Low' ? 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300' :
                          'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                        }`}>{act.priority}</span>
                      </div>
                      <p className="text-sm font-semibold mb-2">{act.task}</p>
                      {act.context && <p className="text-xs text-[var(--text-secondary)] mb-4 opacity-80">{act.context}</p>}
                    </div>
                    <div className="text-xs text-[var(--text-secondary)] flex justify-between items-center border-t border-[var(--border)] pt-3 mt-auto">
                      <span>⏳ {act.deadline || "无期限"}</span>
                      {act.feishu_task_id && <span className="text-green-600 dark:text-green-400">已推飞书</span>}
                      {act.jira_issue_key && <span className="text-blue-600 dark:text-blue-400">{act.jira_issue_key}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Insights Tab (CSS Vis) ── */}
        {activeTab === "insights" && result.insights && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="p-5 rounded-xl bg-[var(--bg-primary)] border border-[var(--border)] flex flex-col items-center justify-center text-center">
                <span className="text-[var(--text-secondary)] text-sm font-bold mb-1">会议效率评分</span>
                <span className="text-4xl font-extrabold text-[var(--accent)]">{result.insights.efficiency_score}/10</span>
              </div>
              <div className="p-5 rounded-xl bg-[var(--bg-primary)] border border-[var(--border)] flex flex-col items-center justify-center text-center">
                <span className="text-[var(--text-secondary)] text-sm font-bold mb-1">整体氛围</span>
                <span className="text-2xl font-bold mt-1 capitalize">{result.insights.overall_sentiment}</span>
              </div>
            </div>

            <div className="p-6 rounded-xl bg-[var(--bg-primary)] border border-[var(--border)]">
              <h3 className="font-bold text-lg mb-4">发言时长分布</h3>
              <div className="space-y-4">
                {result.insights.speaker_stats?.map((stat: any, idx: number) => (
                  <div key={idx}>
                    <div className="flex justify-between text-sm mb-1 font-semibold">
                      <span>{stat.speaker}</span>
                      <span>{Math.round(stat.speaking_ratio * 100)}% ({Math.round(stat.speaking_duration)}s)</span>
                    </div>
                    <div className="h-3 w-full bg-[var(--bg-secondary)] rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-[var(--accent)] rounded-full transition-all duration-1000 ease-out" 
                        style={{ width: `${stat.speaking_ratio * 100}%`, backgroundColor: `hsl(${idx * 45 + 200}, 70%, 50%)` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="font-bold text-sm text-[var(--text-secondary)] mb-3 uppercase tracking-wider">关键词</h3>
              <div className="flex flex-wrap gap-2">
                {result.insights.keywords?.map((kw: string, i: number) => (
                  <span key={i} className="px-3 py-1 bg-[var(--bg-primary)] border border-[var(--border)] rounded-full text-sm font-medium">{kw}</span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Transcript Tab ── */}
        {activeTab === "transcript" && result.diarized_transcript && (
          <div className="animate-in fade-in whitespace-pre-wrap font-mono text-sm leading-relaxed max-h-[600px] overflow-y-auto p-4 bg-[var(--bg-primary)] rounded-xl border border-[var(--border)] shadow-inner">
            {result.diarized_transcript}
          </div>
        )}

        {/* ── Report Tab ── */}
        {activeTab === "report" && (
          <div className="animate-in fade-in">
            <div className="flex flex-wrap gap-2 mb-6">
              <button onClick={handleDownloadMd} className="px-3 py-1.5 text-xs font-bold rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] hover:border-[var(--accent)] transition-colors">
                📥 下载 Markdown
              </button>
              {result.meeting_id && result.output_files?.pdf && (
                <a href={`${API_BASE}/reports/${result.meeting_id}/${result.output_files.pdf.split(/[/\\]/).pop()}`} target="_blank" className="px-3 py-1.5 text-xs font-bold rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] hover:border-[var(--accent)] transition-colors inline-flex items-center">
                  📄 下载 PDF
                </a>
              )}
              {result.meeting_id && result.output_files?.html && (
                <a href={`${API_BASE}/reports/${result.meeting_id}/${result.output_files.html.split(/[/\\]/).pop()}`} target="_blank" className="px-3 py-1.5 text-xs font-bold rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] hover:border-[var(--accent)] transition-colors inline-flex items-center">
                  🌐 查看 HTML
                </a>
              )}
              {result.meeting_id && result.output_files?.mindmap && (
                <a href={`${API_BASE}/reports/${result.meeting_id}/${result.output_files.mindmap.split(/[/\\]/).pop()}`} target="_blank" className="px-3 py-1.5 text-xs font-bold rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] hover:border-[var(--accent)] transition-colors inline-flex items-center">
                  🧠 思维导图
                </a>
              )}
            </div>
            {result.content ? (
              <div className="note-content bg-[var(--bg-primary)] p-8 rounded-2xl shadow-inner border border-[var(--border)] text-base">
                <ReactMarkdown>{result.content}</ReactMarkdown>
              </div>
            ) : (
              <div className="text-center py-12 text-[var(--text-secondary)]">此报告无正文。</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
