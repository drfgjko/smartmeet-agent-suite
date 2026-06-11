import React, { useState, useRef, useCallback } from 'react';
import { Result, InputMode, JobConfigType } from '../types';
import JobConfigPanel from './JobConfigPanel';
import FileInput from './FileInput';
import { useTasks } from './TaskProvider';

type UploadPanelProps = {
  API_BASE: string;
  onSuccess: (r: Result, input: string) => void;
};

export default function UploadPanel({ API_BASE, onSuccess }: UploadPanelProps) {
  const { addTask } = useTasks();
  const [inputMode, setInputMode] = useState<InputMode>("url");
  const [url, setUrl] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const [numSpeakers, setNumSpeakers] = useState<number | undefined>();
  const [denoiseLevel, setDenoiseLevel] = useState(1);

  const defaultChannel = { enabled: false, push_card: false, push_pdf: false, push_mindmap: false };

  const [jobConfig, setJobConfig] = useState<JobConfigType>({
    enable_summary: true,
    enable_actions: true,
    enable_insights: true,
    enable_report_render: true,
    enable_mindmap: false,
    enable_delivery: false,
    enable_task_sync: false,
    feishu: { ...defaultChannel },
    jira: { ...defaultChannel }
  });

  const handleConfigChange = (key: keyof JobConfigType, value: any) => {
    setJobConfig(prev => ({ ...prev, [key]: value }));
  };

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleUrlSubmit = useCallback(async () => {
    if (!url.trim() || loading) return;
    if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") {
      setError("当前为 Vercel 静态演示模式，请在本地部署以使用真实处理能力");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("url", url.trim());
      if (numSpeakers) form.append("num_speakers", String(numSpeakers));
      form.append("denoise_level", String(denoiseLevel));
      form.append("job_config", JSON.stringify(jobConfig));

      const resp = await fetch(`${API_BASE}/api/v1/recording/process/async`, {
        method: "POST",
        body: form,
      });
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({}));
        throw new Error(e.detail || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      addTask(data.task_id, data.meeting_id, url.trim());
      setUrl("");

    } catch (e: any) {
      setError(e.message || "PROCESS FAILED");
    } finally {
      setLoading(false);
    }
  }, [url, numSpeakers, denoiseLevel, jobConfig, loading, API_BASE, onSuccess]);

  const handleFileSubmit = useCallback(async () => {
    if (!uploadFile || loading) return;
    if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") {
      setError("当前为 Vercel 静态演示模式，请在本地部署以使用真实处理能力");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      const uploadResp = await fetch(`${API_BASE}/api/v1/recording/upload`, {
        method: "POST",
        body: formData,
      });
      if (!uploadResp.ok) throw new Error("UPLOAD FAILED");
      const { file_id } = await uploadResp.json();

      const processForm = new FormData();
      processForm.append("file_id", file_id);
      if (numSpeakers)
        processForm.append("num_speakers", String(numSpeakers));
      processForm.append("denoise_level", String(denoiseLevel));
      processForm.append("job_config", JSON.stringify(jobConfig));

      const resp = await fetch(`${API_BASE}/api/v1/recording/process/async`, {
        method: "POST",
        body: processForm,
      });
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({}));
        throw new Error(e.detail || "PROCESS FAILED");
      }

      const data = await resp.json();
      addTask(data.task_id, data.meeting_id, uploadFile.name);
      setUploadFile(null);

    } catch (e: any) {
      setError(e.message || "PROCESS FAILED");
    } finally {
      setLoading(false);
    }
  }, [uploadFile, numSpeakers, denoiseLevel, jobConfig, loading, API_BASE, onSuccess]);

  const handleSubmit = inputMode === "url" ? handleUrlSubmit : handleFileSubmit;

  const canSubmit = !loading && (inputMode === "url" ? url.trim() !== "" : uploadFile !== null);

  return (
    <div className="w-full">
      <div className="flex space-x-4 mb-6">
        <button
          onClick={() => setInputMode("url")}
          className={`flex-1 py-4 font-black border-[3px] border-black transition-all ${
            inputMode === "url"
              ? "bg-[#ffc900] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] translate-x-[-2px] translate-y-[-2px]"
              : "bg-white hover:bg-[#ffc900] hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-2px] hover:translate-y-[-2px]"
          }`}
        >
          在线链接
        </button>
        <button
          onClick={() => setInputMode("file")}
          className={`flex-1 py-4 font-black border-[3px] border-black transition-all ${
            inputMode === "file"
              ? "bg-[#22d3ee] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] translate-x-[-2px] translate-y-[-2px]"
              : "bg-white hover:bg-[#22d3ee] hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-2px] hover:translate-y-[-2px]"
          }`}
        >
          本地文件上传
        </button>
      </div>

      <div className="brutal-box p-8 mb-8">
        {inputMode === "url" && (
          <div>
            <label className="block text-sm font-black mb-3">输入视频/音频链接</label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder="请在此粘贴飞书会议 / 播客 / 哔哩哔哩链接..."
              className="brutal-input text-lg"
            />
          </div>
        )}

        {inputMode === "file" && (
          <FileInput uploadFile={uploadFile} setUploadFile={setUploadFile} />
        )}
      </div>

      <JobConfigPanel 
        numSpeakers={numSpeakers}
        setNumSpeakers={setNumSpeakers}
        denoiseLevel={denoiseLevel}
        setDenoiseLevel={setDenoiseLevel}
        jobConfig={jobConfig}
        handleConfigChange={handleConfigChange}
      />

      <div className="mt-8 flex gap-4">
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="brutal-btn brutal-btn-primary flex-1 text-xl py-5 font-black"
        >
          {loading ? "提交中..." : "启动智能分析"}
        </button>
      </div>

      {error && (
        <div className="mt-6 p-4 border-[3px] border-black bg-red-400 font-black uppercase shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
          ERROR: {error}
        </div>
      )}

    </div>
  );
}
