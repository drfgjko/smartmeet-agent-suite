"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";

const API_BASE =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://api:8000";

const HISTORY_KEY = "smartmeet_history";
const MAX_HISTORY = 50;

type OutputFiles = Record<string, string>;

type Result = {
  title: string;
  content: string;
  source: string;
  duration: number;
  num_speakers?: number;
  speakers?: string[];
  output_files?: OutputFiles;
};

type HistoryItem = Result & {
  id: string;
  input: string;
  timestamp: number;
  contentPreview: string;
};

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

type InputMode = "url" | "file";

export default function Home() {
  const [inputMode, setInputMode] = useState<InputMode>("url");
  const [url, setUrl] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Advanced options
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [numSpeakers, setNumSpeakers] = useState<number | undefined>();
  const [denoiseLevel, setDenoiseLevel] = useState(1);
  const [context, setContext] = useState("");

  // Processing state
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [streamStage, setStreamStage] = useState("");
  const [copied, setCopied] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // UI state
  const [darkMode, setDarkMode] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  // ── URL 模式：SSE 流式处理 ──
  const handleUrlSubmit = useCallback(async () => {
    if (!url.trim() || loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    setStreamStage("正在连接...");
    abortRef.current = new AbortController();
    try {
      const form = new FormData();
      form.append("url", url.trim());
      if (context) form.append("context", context);
      if (numSpeakers) form.append("num_speakers", String(numSpeakers));
      form.append("denoise_level", String(denoiseLevel));

      const resp = await fetch(`${API_BASE}/api/v1/recording/process/stream`, {
        method: "POST",
        body: form,
        signal: abortRef.current.signal,
      });
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({}));
        throw new Error(e.detail || `HTTP ${resp.status}`);
      }
      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No response body");
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6).trim());
            if (ev.stage === "done") {
              const r: Result = {
                title: ev.title || "会议报告",
                content: ev.content || "",
                source: "url",
                duration: ev.duration || 0,
                num_speakers: ev.num_speakers,
                speakers: ev.speakers,
                output_files: ev.output_files,
              };
              setResult(r);
              const items = loadHistory();
              items.unshift({
                ...r,
                id: Date.now().toString(36),
                input: url.trim(),
                timestamp: Date.now(),
                contentPreview: r.content.slice(0, 120).replace(/\n/g, " "),
              });
              saveHistory(items);
              setHistory(loadHistory());
            } else if (ev.stage === "error") {
              throw new Error(ev.message);
            } else {
              setStreamStage(ev.message || "处理中...");
            }
          } catch (pe: any) {
            if (pe.message && !pe.message.includes("JSON")) throw pe;
          }
        }
      }
    } catch (e: any) {
      if (e.name !== "AbortError") setError(e.message || "处理失败");
    } finally {
      setLoading(false);
      setStreamStage("");
      abortRef.current = null;
    }
  }, [url, context, numSpeakers, denoiseLevel, loading]);

  // ── 文件模式：上传 → 处理 ──
  const handleFileSubmit = useCallback(async () => {
    if (!uploadFile || loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    setStreamStage("上传文件...");
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      const uploadResp = await fetch(`${API_BASE}/api/v1/recording/upload`, {
        method: "POST",
        body: formData,
      });
      if (!uploadResp.ok) throw new Error("上传失败");
      const { file_id } = await uploadResp.json();

      setStreamStage("AI 多 Agent 协同分析中...");
      const processForm = new FormData();
      processForm.append("file_id", file_id);
      if (context) processForm.append("context", context);
      if (numSpeakers)
        processForm.append("num_speakers", String(numSpeakers));
      processForm.append("denoise_level", String(denoiseLevel));

      const resp = await fetch(`${API_BASE}/api/v1/recording/process`, {
        method: "POST",
        body: processForm,
      });
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({}));
        throw new Error(e.detail || "处理失败");
      }
      const data = await resp.json();
      const r: Result = {
        title: data.title || uploadFile.name,
        content: data.content || "",
        source: "file",
        duration: data.duration || 0,
        num_speakers: data.num_speakers,
        speakers: data.speakers,
        output_files: data.output_files,
      };
      setResult(r);
      const items = loadHistory();
      items.unshift({
        ...r,
        id: Date.now().toString(36),
        input: uploadFile.name,
        timestamp: Date.now(),
        contentPreview: r.content.slice(0, 120).replace(/\n/g, " "),
      });
      saveHistory(items);
      setHistory(loadHistory());
    } catch (e: any) {
      setError(e.message || "处理失败");
    } finally {
      setLoading(false);
      setStreamStage("");
    }
  }, [uploadFile, context, numSpeakers, denoiseLevel, loading]);

  const handleSubmit = inputMode === "url" ? handleUrlSubmit : handleFileSubmit;

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) setUploadFile(file);
  };

  const handleCancel = () => {
    abortRef.current?.abort();
    setLoading(false);
    setStreamStage("");
  };

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

  const handleDeleteHistory = (id: string) => {
    const updated = history.filter((h) => h.id !== id);
    saveHistory(updated);
    setHistory(updated);
  };

  const handleClearHistory = () => {
    saveHistory([]);
    setHistory([]);
  };

  const canSubmit =
    !loading && (inputMode === "url" ? url.trim() !== "" : uploadFile !== null);

  return (
    <div className={darkMode ? "dark" : ""}>
      <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
        {/* ── Header ── */}
        <header className="border-b border-[var(--border)] bg-[var(--bg-secondary)]">
          <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-3xl">🤖</span>
              <div>
                <h1 className="text-xl font-bold">SmartMeet Agent Suite</h1>
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
                className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors"
              >
                {showHistory ? "返回" : "📋 历史"}
              </button>
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors"
              >
                {darkMode ? "☀️" : "🌙"}
              </button>
            </div>
          </div>
        </header>

        <main className="max-w-5xl mx-auto px-4 py-8">
          {showHistory ? (
            /* ── 历史记录 ── */
            <div>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold">处理历史</h2>
                {history.length > 0 && (
                  <button
                    onClick={handleClearHistory}
                    className="text-sm text-red-500 hover:underline"
                  >
                    清空全部
                  </button>
                )}
              </div>
              {history.length === 0 ? (
                <p className="text-[var(--text-secondary)] text-center py-12">
                  暂无历史记录
                </p>
              ) : (
                <div className="space-y-3">
                  {history.map((h) => (
                    <div
                      key={h.id}
                      className="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] cursor-pointer hover:border-[var(--accent)] transition-colors"
                      onClick={() => {
                        setResult(h);
                        setShowHistory(false);
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm">{h.title}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-[var(--text-secondary)]">
                            {new Date(h.timestamp).toLocaleString("zh-CN")}
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteHistory(h.id);
                            }}
                            className="text-xs text-red-400 hover:text-red-600"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] mt-1 truncate">
                        {h.input} · {h.source === "url" ? "链接" : "文件"} ·{" "}
                        {h.num_speakers
                          ? `${h.num_speakers} 位发言人`
                          : ""}
                      </p>
                      <p className="text-xs text-[var(--text-secondary)] mt-1 line-clamp-2">
                        {h.contentPreview}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : !result ? (
            /* ── 输入区域 ── */
            <div>
              {/* 功能卡片 */}
              <div className="text-center mb-10">
                <h2 className="text-2xl font-bold mb-2">
                  一键生成企业级会议报告
                </h2>
                <p className="text-[var(--text-secondary)] max-w-xl mx-auto">
                  输入音视频链接或上传本地文件，4 个 AI Agent 并行协作：自动生成结构化纪要、提取行动项、分析发言洞察、渲染专业 PDF 讲义与思维导图。
                </p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
                <FC icon="📝" title="结构化纪要" desc="议题、决策、结论" />
                <FC icon="✅" title="行动项提取" desc="谁、何时、做什么" />
                <FC icon="📊" title="发言洞察" desc="时长、情绪、效率" />
                <FC icon="📄" title="专业报告" desc="PDF + 思维导图" />
              </div>

              {/* 输入模式切换 */}
              <div className="max-w-2xl mx-auto">
                <div className="flex gap-1 p-1 bg-[var(--bg-secondary)] rounded-xl mb-4 border border-[var(--border)]">
                  <button
                    onClick={() => setInputMode("url")}
                    className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${
                      inputMode === "url"
                        ? "bg-[var(--accent)] text-white shadow-sm"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    🔗 在线链接
                  </button>
                  <button
                    onClick={() => setInputMode("file")}
                    className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${
                      inputMode === "file"
                        ? "bg-[var(--accent)] text-white shadow-sm"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    📁 上传文件
                  </button>
                </div>

                {/* URL 输入 */}
                {inputMode === "url" && (
                  <div className="space-y-3">
                    <input
                      type="text"
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                      placeholder="粘贴 B站 / YouTube 视频链接..."
                      className="w-full px-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--bg-primary)] focus:outline-none focus:border-[var(--accent)] text-sm transition-colors"
                    />
                  </div>
                )}

                {/* 文件上传 */}
                {inputMode === "file" && (
                  <div
                    className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
                      dragOver
                        ? "border-[var(--accent)] bg-blue-50 dark:bg-blue-950"
                        : "border-[var(--border)]"
                    }`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragOver(true);
                    }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="audio/*,video/*"
                      className="hidden"
                      onChange={(e) =>
                        setUploadFile(e.target.files?.[0] || null)
                      }
                    />
                    {uploadFile ? (
                      <div className="space-y-2">
                        <span className="text-3xl">🎬</span>
                        <p className="font-medium text-sm">{uploadFile.name}</p>
                        <p className="text-xs text-[var(--text-secondary)]">
                          {(uploadFile.size / 1024 / 1024).toFixed(1)} MB ·
                          点击重新选择
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <span className="text-3xl">📂</span>
                        <p className="text-sm text-[var(--text-secondary)]">
                          拖拽音视频文件到此处，或点击选择
                        </p>
                        <p className="text-xs text-[var(--text-secondary)]">
                          支持 MP4 / MP3 / WAV / M4A / WebM 等格式
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* 高级选项 */}
                <div className="mt-4">
                  <button
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="text-xs text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors"
                  >
                    {showAdvanced ? "▾ 收起高级选项" : "▸ 高级选项"}
                  </button>
                  {showAdvanced && (
                    <div className="mt-3 p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] space-y-3">
                      <div className="flex items-center gap-3">
                        <label className="text-xs text-[var(--text-secondary)] w-24 shrink-0">
                          说话人数量
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={20}
                          value={numSpeakers || ""}
                          onChange={(e) =>
                            setNumSpeakers(
                              e.target.value
                                ? parseInt(e.target.value)
                                : undefined
                            )
                          }
                          placeholder="自动检测"
                          className="flex-1 px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm focus:outline-none focus:border-[var(--accent)]"
                        />
                      </div>
                      <div className="flex items-center gap-3">
                        <label className="text-xs text-[var(--text-secondary)] w-24 shrink-0">
                          降噪级别
                        </label>
                        <select
                          value={denoiseLevel}
                          onChange={(e) =>
                            setDenoiseLevel(parseInt(e.target.value))
                          }
                          className="flex-1 px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm focus:outline-none focus:border-[var(--accent)]"
                        >
                          <option value={0}>关闭</option>
                          <option value={1}>标准</option>
                          <option value={2}>强力</option>
                        </select>
                      </div>
                      <div className="flex items-start gap-3">
                        <label className="text-xs text-[var(--text-secondary)] w-24 shrink-0 pt-1.5">
                          补充上下文
                        </label>
                        <textarea
                          value={context}
                          onChange={(e) => setContext(e.target.value)}
                          placeholder="可选：补充会议背景信息，帮助 AI 更准确地理解内容"
                          rows={2}
                          className="flex-1 px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm focus:outline-none focus:border-[var(--accent)] resize-none"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* 提交按钮 */}
                <div className="mt-4 flex gap-2">
                  <button
                    onClick={handleSubmit}
                    disabled={!canSubmit}
                    className={`flex-1 py-3 rounded-xl text-sm font-semibold transition-all ${
                      canSubmit
                        ? "bg-[var(--accent)] text-white hover:opacity-90 shadow-sm"
                        : "bg-gray-300 text-gray-500 cursor-not-allowed dark:bg-gray-700 dark:text-gray-400"
                    }`}
                  >
                    {loading ? "处理中..." : "🚀 一键分析"}
                  </button>
                  {loading && (
                    <button
                      onClick={handleCancel}
                      className="px-4 py-3 rounded-xl text-sm border border-red-300 text-red-500 hover:bg-red-50 transition-colors"
                    >
                      取消
                    </button>
                  )}
                </div>

                {/* 处理进度 */}
                {loading && streamStage && (
                  <div className="mt-4 p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)]">
                    <div className="flex items-center gap-3">
                      <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
                      <span className="text-sm">{streamStage}</span>
                    </div>
                  </div>
                )}

                {/* 错误信息 */}
                {error && (
                  <div className="mt-4 p-4 rounded-xl bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm">
                    ❌ {error}
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* ── 结果展示 ── */
            <div>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-lg font-bold">{result.title}</h2>
                  <div className="flex items-center gap-3 mt-1 text-xs text-[var(--text-secondary)]">
                    {result.duration > 0 && (
                      <span>
                        ⏱️{" "}
                        {Math.floor(result.duration / 60)}分{Math.floor(result.duration % 60)}秒
                      </span>
                    )}
                    {result.num_speakers && (
                      <span>👥 {result.num_speakers} 位发言人</span>
                    )}
                    {result.speakers && result.speakers.length > 0 && (
                      <span>🎙️ {result.speakers.join(", ")}</span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => setResult(null)}
                  className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors"
                >
                  ← 返回
                </button>
              </div>

              {/* 操作栏 */}
              <div className="flex flex-wrap gap-2 mb-4">
                <button
                  onClick={handleCopy}
                  className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors"
                >
                  {copied ? "✅ 已复制" : "📋 复制"}
                </button>
                <button
                  onClick={handleDownloadMd}
                  className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors"
                >
                  📥 下载 Markdown
                </button>
                {result.output_files?.pdf && (
                  <a
                    href={`${API_BASE}/reports/${result.output_files.pdf.split("/").pop()}`}
                    target="_blank"
                    className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors inline-flex items-center"
                  >
                    📄 PDF 报告
                  </a>
                )}
                {result.output_files?.html && (
                  <a
                    href={`${API_BASE}/reports/${result.output_files.html.split("/").pop()}`}
                    target="_blank"
                    className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors inline-flex items-center"
                  >
                    🌐 HTML 报告
                  </a>
                )}
                {result.output_files?.mindmap && (
                  <a
                    href={`${API_BASE}/reports/${result.output_files.mindmap.split("/").pop()}`}
                    target="_blank"
                    className="px-3 py-1.5 text-sm rounded-lg border border-[var(--border)] hover:bg-[var(--bg-secondary)] transition-colors inline-flex items-center"
                  >
                    🧠 思维导图
                  </a>
                )}
              </div>

              {/* Markdown 正文 */}
              {result.content ? (
                <div className="note-content p-6 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]">
                  <ReactMarkdown>{result.content}</ReactMarkdown>
                </div>
              ) : (
                <div className="text-center py-12 text-[var(--text-secondary)]">
                  <p>此会议报告无 Markdown 正文预览。</p>
                  <p className="text-sm mt-1">
                    请通过上方的下载按钮获取 PDF 或 HTML 版本。
                  </p>
                </div>
              )}
            </div>
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

function FC({
  icon,
  title,
  desc,
}: {
  icon: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="bg-[var(--bg-secondary)] rounded-xl p-5 border border-[var(--border)]">
      <span className="text-2xl">{icon}</span>
      <h3 className="font-semibold mt-2">{title}</h3>
      <p className="text-sm text-[var(--text-secondary)] mt-1">{desc}</p>
    </div>
  );
}
