import React, { useState, useRef, useCallback } from 'react';
import { Result, InputMode, JobConfigType } from '../types';
import JobConfigPanel from './JobConfigPanel';
import FileInput from './FileInput';

function FC({ icon, title, desc }: { icon: string; title: string; desc: string; }) {
  return (
    <div className="bg-[var(--bg-secondary)] rounded-2xl p-5 border border-[var(--border)] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all">
      <span className="text-3xl block mb-2">{icon}</span>
      <h3 className="font-bold text-base">{title}</h3>
      <p className="text-xs text-[var(--text-secondary)] mt-1 font-medium">{desc}</p>
    </div>
  );
}

type UploadPanelProps = {
  API_BASE: string;
  onSuccess: (r: Result, input: string) => void;
};

export default function UploadPanel({ API_BASE, onSuccess }: UploadPanelProps) {
  const [inputMode, setInputMode] = useState<InputMode>("url");
  const [url, setUrl] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  // Advanced options state
  const [numSpeakers, setNumSpeakers] = useState<number | undefined>();
  const [denoiseLevel, setDenoiseLevel] = useState(1);
  const [context, setContext] = useState("");

  // JobConfig (Plugin & Node Control)
  const [jobConfig, setJobConfig] = useState<JobConfigType>({
    enable_summary: true,
    enable_actions: true,
    enable_insights: true,
    enable_feishu: true,
    enable_jira: true,
    feishu_app_id: "",
    feishu_app_secret: "",
    feishu_webhook_url: "",
    jira_server: "",
    jira_email: "",
    jira_api_token: ""
  });

  const handleConfigChange = (key: keyof JobConfigType, value: any) => {
    setJobConfig(prev => ({ ...prev, [key]: value }));
  };

  // Processing state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [streamStage, setStreamStage] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  // ── URL 模式：SSE 流式处理 ──
  const handleUrlSubmit = useCallback(async () => {
    if (!url.trim() || loading) return;
    setLoading(true);
    setError("");
    setStreamStage("正在连接...");
    abortRef.current = new AbortController();
    try {
      const form = new FormData();
      form.append("url", url.trim());
      if (context) form.append("context", context);
      if (numSpeakers) form.append("num_speakers", String(numSpeakers));
      form.append("denoise_level", String(denoiseLevel));
      form.append("job_config", JSON.stringify(jobConfig));

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
                meeting_id: ev.meeting_id,
                title: ev.title || "会议报告",
                content: ev.content || "",
                source: "url",
                duration: ev.duration || 0,
                num_speakers: ev.num_speakers,
                speakers: ev.speakers,
                output_files: ev.output_files,
                summary: ev.summary,
                actions: ev.actions,
                insights: ev.insights,
                diarized_transcript: ev.diarized_transcript
              };
              onSuccess(r, url.trim());
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
  }, [url, context, numSpeakers, denoiseLevel, jobConfig, loading, API_BASE, onSuccess]);

  // ── 文件模式：上传 → 处理 ──
  const handleFileSubmit = useCallback(async () => {
    if (!uploadFile || loading) return;
    setLoading(true);
    setError("");
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
      processForm.append("job_config", JSON.stringify(jobConfig));

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
        meeting_id: data.meeting_id,
        title: data.title || uploadFile.name,
        content: data.content || "",
        source: "file",
        duration: data.duration || 0,
        num_speakers: data.num_speakers,
        speakers: data.speakers,
        output_files: data.output_files,
        summary: data.summary,
        actions: data.actions,
        insights: data.insights,
        diarized_transcript: data.diarized_transcript
      };
      onSuccess(r, uploadFile.name);
    } catch (e: any) {
      setError(e.message || "处理失败");
    } finally {
      setLoading(false);
      setStreamStage("");
    }
  }, [uploadFile, context, numSpeakers, denoiseLevel, jobConfig, loading, API_BASE, onSuccess]);

  const handleSubmit = inputMode === "url" ? handleUrlSubmit : handleFileSubmit;

  const handleCancel = () => {
    abortRef.current?.abort();
    setLoading(false);
    setStreamStage("");
  };

  const canSubmit = !loading && (inputMode === "url" ? url.trim() !== "" : uploadFile !== null);

  return (
    <div className="max-w-3xl mx-auto mt-4">
      <div className="text-center mb-12">
        <h2 className="text-3xl font-extrabold mb-3 tracking-tight">
          一键生成企业级会议报告
        </h2>
        <p className="text-[var(--text-secondary)] text-lg">
          上传音视频，让 4 个 AI Agent 为您并行提取纪要、待办与洞察
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
        <FC icon="📝" title="结构化纪要" desc="议题与结论" />
        <FC icon="✅" title="待办提取" desc="任务与死线" />
        <FC icon="📊" title="发言洞察" desc="情绪与占比" />
        <FC icon="📄" title="多端推送" desc="飞书与 Jira" />
      </div>

      <div className="bg-[var(--bg-secondary)] rounded-2xl p-6 border border-[var(--border)] shadow-sm">
        <div className="flex gap-2 p-1 bg-[var(--bg-primary)] rounded-xl mb-6 border border-[var(--border)]">
          <button
            onClick={() => setInputMode("url")}
            className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-bold transition-all ${
              inputMode === "url"
                ? "bg-[var(--accent)] text-white shadow-md transform scale-[1.02]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            🔗 在线链接
          </button>
          <button
            onClick={() => setInputMode("file")}
            className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-bold transition-all ${
              inputMode === "file"
                ? "bg-[var(--accent)] text-white shadow-md transform scale-[1.02]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            📁 上传文件
          </button>
        </div>

        {inputMode === "url" && (
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            placeholder="在此粘贴 B站 / YouTube 等视频链接..."
            className="w-full px-5 py-4 rounded-xl border-2 border-[var(--border)] bg-[var(--bg-primary)] focus:outline-none focus:border-[var(--accent)] text-base transition-colors shadow-inner"
          />
        )}

        {inputMode === "file" && (
          <FileInput uploadFile={uploadFile} setUploadFile={setUploadFile} />
        )}

        {/* ── 高级选项 & 节点配置 ── */}
        <JobConfigPanel 
          numSpeakers={numSpeakers}
          setNumSpeakers={setNumSpeakers}
          denoiseLevel={denoiseLevel}
          setDenoiseLevel={setDenoiseLevel}
          context={context}
          setContext={setContext}
          jobConfig={jobConfig}
          handleConfigChange={handleConfigChange}
        />

        {/* 提交按钮 */}
        <div className="mt-6 flex gap-3">
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className={`flex-1 py-4 rounded-xl text-base font-bold transition-all transform ${
              canSubmit
                ? "bg-[var(--accent)] text-white hover:opacity-90 shadow-lg hover:shadow-xl hover:-translate-y-0.5"
                : "bg-gray-300 text-gray-500 cursor-not-allowed dark:bg-gray-800 dark:text-gray-500"
            }`}
          >
            {loading ? "处理中..." : "🚀 开始智能分析"}
          </button>
          {loading && (
            <button
              onClick={handleCancel}
              className="px-6 py-4 rounded-xl text-sm font-bold border-2 border-red-200 text-red-500 hover:bg-red-50 hover:border-red-300 dark:hover:bg-red-900/20 transition-all"
            >
              取消
            </button>
          )}
        </div>

        {/* 处理进度 */}
        {loading && streamStage && (
          <div className="mt-6 p-4 rounded-xl bg-[var(--bg-primary)] border border-[var(--border)] shadow-inner">
            <div className="flex items-center justify-center gap-3">
              <div className="w-5 h-5 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
              <span className="text-sm font-medium tracking-wide">{streamStage}</span>
            </div>
          </div>
        )}

        {/* 错误信息 */}
        {error && (
          <div className="mt-6 p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border-2 border-red-200 dark:border-red-800/50 text-red-600 dark:text-red-400 text-sm font-semibold animate-in shake">
            ❌ {error}
          </div>
        )}
      </div>
    </div>
  );
}
