import React from "react";
import { Result } from "../../types";

type MeetingOverviewProps = {
  result: Result;
};

/** 将秒数格式化为"X分Y秒" */
function formatDuration(secs: number): string {
  if (!secs || secs <= 0) return "--";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  if (m === 0) return `${s}秒`;
  return s > 0 ? `${m}分${s}秒` : `${m}分`;
}

export default function MeetingOverview({ result }: MeetingOverviewProps) {
  const score = result.insights?.efficiency_score;
  const keywords: string[] = result.insights?.keywords ?? [];

  return (
    <div className="brutal-box p-5 bg-white space-y-5">
      {/* 区块标题 */}
      <h2 className="text-sm font-black uppercase tracking-widest text-gray-400 border-b-[2px] border-black pb-2">
        会议概览
      </h2>

      {/* 效率评分 */}
      {score !== undefined && score !== null && (
        <div className="flex items-end justify-between">
          <span className="text-xs font-black text-gray-500 uppercase">效率评分</span>
          <span className="text-2xl font-black leading-none">
            <span
              className="text-4xl"
              style={{ color: score >= 8 ? "#22c55e" : score >= 6 ? "#ffc900" : "#ef4444" }}
            >
              {score}
            </span>
            <span className="text-base text-gray-400 ml-1">/ 10</span>
          </span>
        </div>
      )}

      {/* 核心指标网格 */}
      <div className="grid grid-cols-2 gap-3">
        <MetricCell label="时长" value={formatDuration(result.duration)} />
        <MetricCell label="发言人数" value={result.num_speakers ? `${result.num_speakers} 人` : "--"} />
        {result.insights?.overall_sentiment && (
          <MetricCell
            label="整体氛围"
            value={result.insights.overall_sentiment}
            className="col-span-2"
          />
        )}
      </div>

      {/* 关键词 */}
      {keywords.length > 0 && (
        <div>
          <span className="text-xs font-black text-gray-400 uppercase tracking-widest block mb-2">
            关键词
          </span>
          <div className="flex flex-wrap gap-2">
            {keywords.slice(0, 12).map((kw, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs font-bold border-[2px] border-black bg-[#ffc900] shadow-[2px_2px_0px_rgba(0,0,0,1)]"
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 发言人列表 */}
      {result.speakers && result.speakers.length > 0 && (
        <div>
          <span className="text-xs font-black text-gray-400 uppercase tracking-widest block mb-2">
            发言人
          </span>
          <div className="flex flex-wrap gap-1">
            {result.speakers.map((sp, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs font-bold border-[2px] border-black bg-white shadow-[2px_2px_0px_rgba(0,0,0,1)]"
              >
                {sp}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** 单个指标格子 */
function MetricCell({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div
      className={`border-[2px] border-black px-3 py-2 bg-[#f4f4f0] shadow-[2px_2px_0px_rgba(0,0,0,1)] ${className}`}
    >
      <div className="text-[10px] font-black uppercase tracking-widest text-gray-400">{label}</div>
      <div className="text-sm font-black mt-0.5 truncate">{value}</div>
    </div>
  );
}
