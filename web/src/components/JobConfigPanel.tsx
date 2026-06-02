import React, { useState } from 'react';
import { JobConfigType } from '../types';

type JobConfigPanelProps = {
  numSpeakers: number | undefined;
  setNumSpeakers: (v: number | undefined) => void;
  denoiseLevel: number;
  setDenoiseLevel: (v: number) => void;
  context: string;
  setContext: (v: string) => void;
  jobConfig: JobConfigType;
  handleConfigChange: (key: keyof JobConfigType, value: any) => void;
};

export default function JobConfigPanel({
  numSpeakers, setNumSpeakers,
  denoiseLevel, setDenoiseLevel,
  context, setContext,
  jobConfig, handleConfigChange
}: JobConfigPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <div className="mt-6 border-t border-[var(--border)] pt-4">
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="text-sm font-semibold text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors flex items-center gap-1"
      >
        {showAdvanced ? "▾ 收起配置" : "▸ 高级选项与节点配置"}
      </button>
      {showAdvanced && (
        <div className="mt-4 grid gap-6 animate-in slide-in-from-top-2">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-semibold text-[var(--text-secondary)] block">发言人数量</label>
              <input
                type="number" min={1} max={20} value={numSpeakers || ""}
                onChange={(e) => setNumSpeakers(e.target.value ? parseInt(e.target.value) : undefined)}
                placeholder="自动推断"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm focus:outline-none focus:border-[var(--accent)]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-semibold text-[var(--text-secondary)] block">降噪级别</label>
              <select
                value={denoiseLevel}
                onChange={(e) => setDenoiseLevel(parseInt(e.target.value))}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm focus:outline-none focus:border-[var(--accent)]"
              >
                <option value={0}>关闭 (0)</option>
                <option value={1}>标准 (1)</option>
                <option value={2}>强力 (2)</option>
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-[var(--text-secondary)] block">会议补充上下文</label>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="可选：补充会议背景信息，帮助 AI 准确理解专有名词"
              rows={2}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg-primary)] text-sm focus:outline-none focus:border-[var(--accent)] resize-none"
            />
          </div>

          <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--bg-primary)]">
            <h4 className="text-sm font-bold mb-3 border-b border-[var(--border)] pb-2">AI 节点控制</h4>
            <div className="flex flex-wrap gap-4 mb-4">
              <label className="flex items-center gap-2 text-sm cursor-pointer hover:text-[var(--accent)]">
                <input type="checkbox" checked={jobConfig.enable_summary} onChange={(e) => handleConfigChange("enable_summary", e.target.checked)} className="rounded" />
                生成纪要
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer hover:text-[var(--accent)]">
                <input type="checkbox" checked={jobConfig.enable_actions} onChange={(e) => handleConfigChange("enable_actions", e.target.checked)} className="rounded" />
                提取待办
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer hover:text-[var(--accent)]">
                <input type="checkbox" checked={jobConfig.enable_insights} onChange={(e) => handleConfigChange("enable_insights", e.target.checked)} className="rounded" />
                会议洞察
              </label>
            </div>

            <h4 className="text-sm font-bold mb-3 mt-4 border-b border-[var(--border)] pb-2">外部集成配置 (可选)</h4>
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-semibold cursor-pointer">
                  <input type="checkbox" checked={jobConfig.enable_feishu} onChange={(e) => handleConfigChange("enable_feishu", e.target.checked)} className="rounded text-[var(--accent)]" />
                  启用飞书推送
                </label>
                {jobConfig.enable_feishu && (
                  <div className="grid grid-cols-2 gap-2 pl-6 animate-in fade-in">
                    <input type="text" placeholder="Feishu App ID" value={jobConfig.feishu_app_id} onChange={(e) => handleConfigChange("feishu_app_id", e.target.value)} className="px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-secondary)]" />
                    <input type="password" placeholder="Feishu App Secret" value={jobConfig.feishu_app_secret} onChange={(e) => handleConfigChange("feishu_app_secret", e.target.value)} className="px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-secondary)]" />
                    <input type="text" placeholder="Webhook URL (可选)" value={jobConfig.feishu_webhook_url} onChange={(e) => handleConfigChange("feishu_webhook_url", e.target.value)} className="col-span-2 px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-secondary)]" />
                  </div>
                )}
              </div>
              
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-semibold cursor-pointer">
                  <input type="checkbox" checked={jobConfig.enable_jira} onChange={(e) => handleConfigChange("enable_jira", e.target.checked)} className="rounded text-[var(--accent)]" />
                  启用 Jira 同步
                </label>
                {jobConfig.enable_jira && (
                  <div className="grid grid-cols-2 gap-2 pl-6 animate-in fade-in">
                    <input type="text" placeholder="Jira Server URL" value={jobConfig.jira_server} onChange={(e) => handleConfigChange("jira_server", e.target.value)} className="col-span-2 px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-secondary)]" />
                    <input type="text" placeholder="Jira Email" value={jobConfig.jira_email} onChange={(e) => handleConfigChange("jira_email", e.target.value)} className="px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-secondary)]" />
                    <input type="password" placeholder="Jira API Token" value={jobConfig.jira_api_token} onChange={(e) => handleConfigChange("jira_api_token", e.target.value)} className="px-3 py-1.5 text-xs rounded border border-[var(--border)] bg-[var(--bg-secondary)]" />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
