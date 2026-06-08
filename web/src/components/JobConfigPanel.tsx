import React, { useState } from 'react';
import { JobConfigType } from '../types';
import BrutalCheckbox from './ui/BrutalCheckbox';

type JobConfigPanelProps = {
  numSpeakers: number | undefined;
  setNumSpeakers: (v: number | undefined) => void;
  denoiseLevel: number;
  setDenoiseLevel: (v: number) => void;
  jobConfig: JobConfigType;
  handleConfigChange: (key: keyof JobConfigType, value: any) => void;
};

export default function JobConfigPanel({
  numSpeakers, setNumSpeakers,
  denoiseLevel, setDenoiseLevel,
  jobConfig, handleConfigChange
}: JobConfigPanelProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <div className="brutal-box p-6 bg-white">
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="w-full text-left font-black text-lg flex justify-between items-center"
      >
        <span>高级配置与节点开关</span>
        <span>{showAdvanced ? "[-]" : "[+]"}</span>
      </button>

      {showAdvanced && (
        <div className="mt-6 border-t-[3px] border-black pt-6 grid gap-6">
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-black block">发言人数量</label>
              <input
                type="number" min={1} max={20} value={numSpeakers || ""}
                onChange={(e) => setNumSpeakers(e.target.value ? parseInt(e.target.value) : undefined)}
                placeholder="自动推断"
                className="brutal-input py-2"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-black block">降噪级别</label>
              <select
                value={denoiseLevel}
                onChange={(e) => setDenoiseLevel(parseInt(e.target.value))}
                className="brutal-input py-2"
              >
                <option value={0}>关闭 (0)</option>
                <option value={1}>标准降噪 (1)</option>
                <option value={2}>强力降噪 (2)</option>
              </select>
            </div>
          </div>

          <div className="p-4 border-[3px] border-black bg-[#f4f4f0]">
            <h4 className="text-sm font-black mb-4">执行节点控制</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <BrutalCheckbox size="lg" checked={jobConfig.enable_summary} onChange={(c) => handleConfigChange("enable_summary", c)} label="全文纪要 (AI)" title="调用 SummaryAgent" />
              <BrutalCheckbox size="lg" checked={jobConfig.enable_actions} onChange={(c) => handleConfigChange("enable_actions", c)} label="提取待办 (AI)" title="调用 ActionAgent" />
              <BrutalCheckbox size="lg" checked={jobConfig.enable_insights} onChange={(c) => handleConfigChange("enable_insights", c)} label="智能洞察 (AI)" title="调用 InsightAgent" />
              <BrutalCheckbox size="lg" checked={jobConfig.enable_report_render} onChange={(c) => handleConfigChange("enable_report_render", c)} label="排版渲染引擎" title="生成 Markdown / PDF / HTML" />
              <BrutalCheckbox size="lg" checked={jobConfig.enable_mindmap} onChange={(c) => handleConfigChange("enable_mindmap", c)} label="生成思维导图" title="调用 MindMapService 生成脑图" />
              <BrutalCheckbox size="lg" checked={jobConfig.enable_task_sync} onChange={(c) => handleConfigChange("enable_task_sync", c)} label="任务系统同步" title="同步 Action 到 Jira/飞书任务" />
              <BrutalCheckbox size="lg" checked={jobConfig.enable_delivery} onChange={(c) => handleConfigChange("enable_delivery", c)} label="报告多端分发" title="通过飞书/Jira分发报告" className="col-span-2 sm:col-span-1" />
            </div>
            
            {/* 分发细粒度配置（当开启分发时出现） */}
            {jobConfig.enable_delivery && (
              <div className="mt-4 pt-4 border-t-[3px] border-black animate-in fade-in">
                <h5 className="text-sm font-black mb-3">飞书机器人推送选项：</h5>
                <div className="flex flex-wrap gap-4 ml-2">
                  <BrutalCheckbox size="md" checked={jobConfig.feishu.enabled} onChange={(c) => handleConfigChange("feishu", { ...jobConfig.feishu, enabled: c })} label="启用飞书" />
                  <BrutalCheckbox size="md" disabled={!jobConfig.feishu.enabled} checked={jobConfig.feishu.push_card} onChange={(c) => handleConfigChange("feishu", { ...jobConfig.feishu, push_card: c })} label="推送总结卡片" />
                  <BrutalCheckbox size="md" disabled={!jobConfig.feishu.enabled} checked={jobConfig.feishu.push_pdf} onChange={(c) => handleConfigChange("feishu", { ...jobConfig.feishu, push_pdf: c })} label="附带 PDF 报告" />
                  <BrutalCheckbox size="md" disabled={!jobConfig.feishu.enabled} checked={jobConfig.feishu.push_mindmap} onChange={(c) => handleConfigChange("feishu", { ...jobConfig.feishu, push_mindmap: c })} label="附带思维导图" />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
