import React from "react";

type SpeakerStat = {
  speaker: string;
  speaking_duration: number;
  speaking_ratio: number;
};

type SpeakerStatsProps = {
  stats: SpeakerStat[];
};

/** 根据下标生成固定的 Neo-brutalism 调色板颜色 */
const PALETTE = [
  "#ff90e8", // 粉
  "#ffc900", // 黄
  "#22d3ee", // 青
  "#c084fc", // 紫
  "#4ade80", // 绿
  "#f87171", // 红
  "#fb923c", // 橙
  "#818cf8", // 蓝紫
];

function getColor(idx: number): string {
  return PALETTE[idx % PALETTE.length];
}

/** 秒数转 "Xm Ys" */
function fmtSecs(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  if (m === 0) return `${s}s`;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

export default function SpeakerStats({ stats }: SpeakerStatsProps) {
  if (!stats || stats.length === 0) return null;

  // 按发言时长降序排列
  const sorted = [...stats].sort((a, b) => b.speaking_duration - a.speaking_duration);

  return (
    <div className="brutal-box p-5 bg-white">
      <h2 className="text-sm font-black uppercase tracking-widest text-gray-400 border-b-[2px] border-black pb-2 mb-4">
        发言人统计
      </h2>

      {/* 环形/堆叠色块 — 简单的色块比例条 */}
      <div className="flex h-3 rounded-none overflow-hidden border-[2px] border-black mb-5">
        {sorted.map((s, i) => (
          <div
            key={i}
            title={`${s.speaker} ${Math.round(s.speaking_ratio * 100)}%`}
            style={{
              width: `${s.speaking_ratio * 100}%`,
              backgroundColor: getColor(i),
            }}
          />
        ))}
      </div>

      {/* 发言人列表 */}
      <div className="space-y-3">
        {sorted.map((s, i) => (
          <div key={i}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                {/* 颜色标识块 */}
                <span
                  className="inline-block w-3 h-3 border-[1.5px] border-black flex-shrink-0"
                  style={{ backgroundColor: getColor(i) }}
                />
                <span className="text-xs font-black truncate max-w-[100px]">{s.speaker}</span>
              </div>
              <div className="flex items-center gap-2 text-xs font-bold text-gray-500">
                <span>{fmtSecs(s.speaking_duration)}</span>
                <span className="text-gray-300">|</span>
                <span className="font-black text-black">{Math.round(s.speaking_ratio * 100)}%</span>
              </div>
            </div>

            {/* 进度条 */}
            <div className="h-2 bg-gray-100 border-[1.5px] border-black overflow-hidden">
              <div
                className="h-full transition-all duration-700 ease-out"
                style={{
                  width: `${s.speaking_ratio * 100}%`,
                  backgroundColor: getColor(i),
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
