import React, { useState } from "react";
import { Result } from "../../types";
import BrutalCheckbox from "../ui/BrutalCheckbox";
import BrutalButton from "../ui/BrutalButton";

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
        <BrutalButton
          id="export-copy-btn"
          onClick={handleCopy}
          accent="#22d3ee"
          disabled={!content}
        >
          {copyState === "ok" ? "已复制!" : copyState === "error" ? "失败" : "复制纪要"}
        </BrutalButton>

        {/* 下载 Markdown */}
        <BrutalButton
          id="export-md-btn"
          onClick={handleDownloadMd}
          accent="#ffc900"
          disabled={!content}
        >
          下载 MD
        </BrutalButton>

        {/* 下载 PDF */}
        <BrutalButton
          id="export-pdf-btn"
          href={hasPdf ? buildFileUrl(output_files!.pdf!) : undefined}
          disabled={!hasPdf}
          accent="#ff90e8"
        >
          下载 PDF
        </BrutalButton>

        {/* 在线 HTML */}
        <BrutalButton
          id="export-html-btn"
          href={hasHtml ? buildFileUrl(output_files!.html!) : undefined}
          disabled={!hasHtml}
          accent="#c084fc"
        >
          HTML 报告
        </BrutalButton>

        {/* 思维导图 */}
        <BrutalButton
          id="export-mindmap-btn"
          href={hasMindmap ? buildFileUrl(output_files!.mindmap!) : undefined}
          disabled={!hasMindmap}
          accent="#4ade80"
          className="col-span-2"
        >
          思维导图
        </BrutalButton>
      </div>

      <div className="mt-4 pt-4 border-t-[2px] border-black/10">
        <h3 className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-3">
          协同发布
        </h3>
        
        {/* 飞书推送配置项 */}
        <div className="flex gap-4 mb-3 text-gray-600">
          <BrutalCheckbox
            size="sm"
            label="推送总结卡片"
            checked={feishuConfig.push_card}
            onChange={(checked) => setFeishuConfig(p => ({ ...p, push_card: checked }))}
          />
          <BrutalCheckbox
            size="sm"
            label="附带 PDF"
            checked={!!output_files?.pdf && feishuConfig.push_pdf}
            onChange={(checked) => setFeishuConfig(p => ({ ...p, push_pdf: checked }))}
            disabled={!output_files?.pdf}
          />
          <BrutalCheckbox
            size="sm"
            label="附带导图"
            checked={!!output_files?.mindmap && feishuConfig.push_mindmap}
            onChange={(checked) => setFeishuConfig(p => ({ ...p, push_mindmap: checked }))}
            disabled={!output_files?.mindmap}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          {/* 推送飞书 */}
          <BrutalButton
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
          </BrutalButton>

          {/* 同步 Jira */}
          <BrutalButton
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
          </BrutalButton>
        </div>
      </div>
    </div>
  );
}


