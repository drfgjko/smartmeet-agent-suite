import React, { useState } from "react";
import { Result } from "../../types";

type ExportActionsProps = {
  result: Result;
  API_BASE: string;
};

type BtnState = "idle" | "loading" | "ok" | "error";

export default function ExportActions({ result, API_BASE }: ExportActionsProps) {
  const [copyState, setCopyState] = useState<BtnState>("idle");
  const [feishuState, setFeishuState] = useState<BtnState>("idle");
  const [jiraState, setJiraState] = useState<BtnState>("idle");

  // 飞书推送配置状态
  const [feishuConfig, setFeishuConfig] = useState({
    push_card: true,
    push_pdf: true,
    push_mindmap: true,
  });

  const { meeting_id, title, content, output_files } = result;

  const handleManualDeliver = async (type: "feishu" | "jira") => {
    const setState = type === "feishu" ? setFeishuState : setJiraState;
    setState("loading");
    try {
      const payload = {
        meeting_id,
        summary: result.summary || {},
        actions: result.actions || {},
        insights: result.insights || {},
        output_files: result.output_files || {},
        job_config: {
          enable_delivery: type === "feishu",
          enable_task_sync: type === "jira",
          feishu: type === "feishu" ? {
            enabled: true,
            ...feishuConfig
          } : undefined,
        },
      };

      const res = await fetch(`${API_BASE}/api/v1/deliver`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setState("ok");
        setTimeout(() => setState("idle"), 3000);
      } else {
        setState("error");
        setTimeout(() => setState("idle"), 3000);
      }
    } catch {
      setState("error");
      setTimeout(() => setState("idle"), 3000);
    }
  };

  /** 下载 Markdown */
  const handleDownloadMd = () => {
    if (!content) return;
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${title || "report"}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  /** 复制纪要文本 */
  const handleCopy = async () => {
    if (!content) return;
    setCopyState("loading");
    try {
      await navigator.clipboard.writeText(content);
      setCopyState("ok");
      setTimeout(() => setCopyState("idle"), 2000);
    } catch {
      setCopyState("error");
      setTimeout(() => setCopyState("idle"), 2000);
    }
  };

  /** 后端文件下载链接（从绝对路径中提取文件名） */
  function buildFileUrl(filePath: string): string {
    const filename = filePath.split(/[/\\]/).pop() ?? filePath;
    return `${API_BASE}/api/v1/reports/${meeting_id}/${filename}`;
  }

  const hasPdf = !!output_files?.pdf && !!meeting_id;
  const hasHtml = !!output_files?.html && !!meeting_id;
  const hasMindmap = !!output_files?.mindmap && !!meeting_id;

  return (
    <div className="brutal-box p-5 bg-white">
      <h2 className="text-sm font-black uppercase tracking-widest text-gray-400 border-b-[2px] border-black pb-2 mb-4">
        操作
      </h2>

      <div className="grid grid-cols-2 gap-3">
        {/* 复制纪要 */}
        <ActionBtn
          id="export-copy-btn"
          onClick={handleCopy}
          accent="#22d3ee"
          disabled={!content}
        >
          {copyState === "ok" ? "已复制!" : copyState === "error" ? "失败" : "复制纪要"}
        </ActionBtn>

        {/* 下载 Markdown */}
        <ActionBtn
          id="export-md-btn"
          onClick={handleDownloadMd}
          accent="#ffc900"
          disabled={!content}
        >
          下载 MD
        </ActionBtn>

        {/* 下载 PDF */}
        {hasPdf ? (
          <a
            id="export-pdf-link"
            href={buildFileUrl(output_files!.pdf!)}
            target="_blank"
            rel="noreferrer"
            className="export-action-btn"
            style={{ "--accent": "#ff90e8" } as React.CSSProperties}
          >
            下载 PDF
          </a>
        ) : (
          <ActionBtn id="export-pdf-btn" disabled accent="#ff90e8">下载 PDF</ActionBtn>
        )}

        {/* 在线 HTML */}
        {hasHtml ? (
          <a
            id="export-html-link"
            href={buildFileUrl(output_files!.html!)}
            target="_blank"
            rel="noreferrer"
            className="export-action-btn"
            style={{ "--accent": "#c084fc" } as React.CSSProperties}
          >
            HTML 报告
          </a>
        ) : (
          <ActionBtn id="export-html-btn" disabled accent="#c084fc">HTML 报告</ActionBtn>
        )}

        {/* 思维导图 */}
        {hasMindmap ? (
          <a
            id="export-mindmap-link"
            href={buildFileUrl(output_files!.mindmap!)}
            target="_blank"
            rel="noreferrer"
            className="export-action-btn col-span-2"
            style={{ "--accent": "#4ade80" } as React.CSSProperties}
          >
            思维导图
          </a>
        ) : (
          <ActionBtn id="export-mindmap-btn" disabled accent="#4ade80" className="col-span-2">
            思维导图
          </ActionBtn>
        )}
      </div>

      <div className="mt-4 pt-4 border-t-[2px] border-black/10">
        <h3 className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-3">
          协同发布
        </h3>
        
        {/* 飞书推送配置项 */}
        <div className="flex gap-4 mb-3 text-[10px] font-bold text-gray-600">
          <label className="flex items-center gap-1.5 cursor-pointer hover:text-black">
            <input 
              type="checkbox" 
              className="accent-black w-3 h-3 border-black border-[1.5px]" 
              checked={feishuConfig.push_card}
              onChange={(e) => setFeishuConfig(p => ({ ...p, push_card: e.target.checked }))}
            />
            推送总结卡片
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer hover:text-black">
            <input 
              type="checkbox" 
              className="accent-black w-3 h-3 border-black border-[1.5px]"
              checked={!!output_files?.pdf && feishuConfig.push_pdf}
              onChange={(e) => setFeishuConfig(p => ({ ...p, push_pdf: e.target.checked }))}
              disabled={!output_files?.pdf}
            />
            附带 PDF
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer hover:text-black">
            <input 
              type="checkbox" 
              className="accent-black w-3 h-3 border-black border-[1.5px]"
              checked={!!output_files?.mindmap && feishuConfig.push_mindmap}
              onChange={(e) => setFeishuConfig(p => ({ ...p, push_mindmap: e.target.checked }))}
              disabled={!output_files?.mindmap}
            />
            附带导图
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {/* 推送飞书 */}
          <ActionBtn
            id="export-feishu-btn"
            onClick={() => handleManualDeliver("feishu")}
            accent="#4ade80"
            disabled={feishuState === "loading"}
          >
            {feishuState === "loading"
              ? "推送中..."
              : feishuState === "ok"
              ? "已推送!"
              : feishuState === "error"
              ? "推送失败"
              : "🚀 推送飞书卡片"}
          </ActionBtn>

          {/* 同步 Jira */}
          <ActionBtn
            id="export-jira-btn"
            onClick={() => handleManualDeliver("jira")}
            accent="#22d3ee"
            disabled={jiraState === "loading" || !result.actions?.action_items?.length}
          >
            {jiraState === "loading"
              ? "同步中..."
              : jiraState === "ok"
              ? "已同步!"
              : jiraState === "error"
              ? "同步失败"
              : "➕ 同步待办至 Jira"}
          </ActionBtn>
        </div>
      </div>
    </div>
  );
}

/** 通用操作按钮 */
function ActionBtn({
  id,
  children,
  onClick,
  disabled,
  accent,
  className = "",
}: {
  id: string;
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  accent: string;
  className?: string;
}) {
  return (
    <button
      id={id}
      onClick={onClick}
      disabled={disabled}
      className={`text-xs font-black py-2.5 px-3 border-[2px] border-black transition-all
        shadow-[2px_2px_0px_rgba(0,0,0,1)]
        hover:shadow-[4px_4px_0px_rgba(0,0,0,1)] hover:translate-x-[-2px] hover:translate-y-[-2px]
        active:shadow-none active:translate-x-0 active:translate-y-0
        disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-[2px_2px_0px_rgba(0,0,0,1)] disabled:hover:translate-x-0 disabled:hover:translate-y-0
        ${className}`}
      style={{ backgroundColor: accent }}
    >
      {children}
    </button>
  );
}
