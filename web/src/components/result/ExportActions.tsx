import React, { useState } from "react";
import { Result } from "../../types";

type ExportActionsProps = {
  result: Result;
  API_BASE: string;
};

type BtnState = "idle" | "loading" | "ok" | "error";

export default function ExportActions({ result, API_BASE }: ExportActionsProps) {
  const [copyState, setCopyState] = useState<BtnState>("idle");

  const { meeting_id, title, content, output_files } = result;

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
