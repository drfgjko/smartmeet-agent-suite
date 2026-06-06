import React, { useState } from 'react';
import { JobConfigType } from '../types';

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
              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={jobConfig.enable_summary} onChange={(e) => handleConfigChange("enable_summary", e.target.checked)} className="w-5 h-5 border-2 border-black accent-black" />
                <span className="font-bold text-sm" title="调用 SummaryAgent">全文纪要 (AI)</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={jobConfig.enable_actions} onChange={(e) => handleConfigChange("enable_actions", e.target.checked)} className="w-5 h-5 border-2 border-black accent-black" />
                <span className="font-bold text-sm" title="调用 ActionAgent">提取待办 (AI)</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={jobConfig.enable_insights} onChange={(e) => handleConfigChange("enable_insights", e.target.checked)} className="w-5 h-5 border-2 border-black accent-black" />
                <span className="font-bold text-sm" title="调用 InsightAgent">智能洞察 (AI)</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={jobConfig.enable_report_render} onChange={(e) => handleConfigChange("enable_report_render", e.target.checked)} className="w-5 h-5 border-2 border-black accent-black" />
                <span className="font-bold text-sm" title="生成 Markdown / PDF / HTML">排版渲染引擎</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={jobConfig.enable_mindmap} onChange={(e) => handleConfigChange("enable_mindmap", e.target.checked)} className="w-5 h-5 border-2 border-black accent-black" />
                <span className="font-bold text-sm" title="调用 MindMapService 生成脑图">生成思维导图</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input type="checkbox" checked={jobConfig.enable_task_sync} onChange={(e) => handleConfigChange("enable_task_sync", e.target.checked)} className="w-5 h-5 border-2 border-black accent-black" />
                <span className="font-bold text-sm" title="同步 Action 到 Jira/飞书任务">任务系统同步</span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer col-span-2 sm:col-span-1">
                <input type="checkbox" checked={jobConfig.enable_delivery} onChange={(e) => handleConfigChange("enable_delivery", e.target.checked)} className="w-5 h-5 border-2 border-black accent-black" />
                <span className="font-bold text-sm" title="通过飞书/Jira分发报告">报告多端分发</span>
              </label>
            </div>
            
            {/* 分发细粒度配置（当开启分发时出现） */}
            {jobConfig.enable_delivery && (
              <div className="mt-4 pt-4 border-t-[3px] border-black animate-in fade-in">
                <h5 className="text-sm font-black mb-3">飞书机器人推送选项：</h5>
                <div className="flex flex-wrap gap-4 ml-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={jobConfig.feishu.enabled} onChange={(e) => handleConfigChange("feishu", { ...jobConfig.feishu, enabled: e.target.checked })} className="w-4 h-4 border-2 border-black accent-black" />
                    <span className="font-bold text-xs">启用飞书</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer" style={{ opacity: jobConfig.feishu.enabled ? 1 : 0.4 }}>
                    <input type="checkbox" disabled={!jobConfig.feishu.enabled} checked={jobConfig.feishu.push_card} onChange={(e) => handleConfigChange("feishu", { ...jobConfig.feishu, push_card: e.target.checked })} className="w-4 h-4 border-2 border-black accent-black" />
                    <span className="font-bold text-xs">推送总结卡片</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer" style={{ opacity: jobConfig.feishu.enabled ? 1 : 0.4 }}>
                    <input type="checkbox" disabled={!jobConfig.feishu.enabled} checked={jobConfig.feishu.push_pdf} onChange={(e) => handleConfigChange("feishu", { ...jobConfig.feishu, push_pdf: e.target.checked })} className="w-4 h-4 border-2 border-black accent-black" />
                    <span className="font-bold text-xs">附带 PDF 报告</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer" style={{ opacity: jobConfig.feishu.enabled ? 1 : 0.4 }}>
                    <input type="checkbox" disabled={!jobConfig.feishu.enabled} checked={jobConfig.feishu.push_mindmap} onChange={(e) => handleConfigChange("feishu", { ...jobConfig.feishu, push_mindmap: e.target.checked })} className="w-4 h-4 border-2 border-black accent-black" />
                    <span className="font-bold text-xs">附带思维导图</span>
                  </label>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
