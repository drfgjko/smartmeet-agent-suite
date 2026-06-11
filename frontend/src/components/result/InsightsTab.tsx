import React from "react";

type SpeakerStat = {
  speaker: string;
  speaking_duration: number;
  speaking_ratio: number;
  segment_count?: number;
};

type InsightsData = {
  efficiency_score?: number;
  overall_sentiment?: string;
  sentiment_score?: number;
  keywords?: string[];
  highlights?: string[];
  suggestions?: string[];
  speaker_stats?: SpeakerStat[];
};

type InsightsTabProps = {
  insights: InsightsData;
};

/** 效率评分 → 颜色 */
function scoreColor(score: number): string {
  if (score >= 8) return "#4ade80";
  if (score >= 6) return "#ffc900";
  return "#f87171";
}

/** 效率评分 → 文字评价 */
function scoreLabel(score: number): string {
  if (score >= 9) return "极高效";
  if (score >= 8) return "高效";
  if (score >= 6) return "一般";
  if (score >= 4) return "低效";
  return "极低效";
}

const PALETTE = ["#ff90e8","#ffc900","#22d3ee","#c084fc","#4ade80","#f87171","#fb923c","#818cf8"];
function getColor(idx: number) { return PALETTE[idx % PALETTE.length]; }

function fmtSecs(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return m > 0 ? (sec > 0 ? `${m}m ${sec}s` : `${m}m`) : `${sec}s`;
}

export default function InsightsTab({ insights }: InsightsTabProps) {
  if (!insights) {
    return (
      <p className="text-xs font-bold text-gray-400 text-center py-12">
        暂无洞察数据
      </p>
    );
  }

  const {
    efficiency_score,
    overall_sentiment,
    sentiment_score,
    keywords,
    highlights,
    suggestions,
    speaker_stats,
  } = insights;

  const sorted = [...(speaker_stats ?? [])].sort(
    (a, b) => b.speaking_duration - a.speaking_duration
  );

  return (
    <div className="space-y-5">
      {/* 核心指标卡片组 */}
      <div className="grid grid-cols-2 gap-3">
        {/* 效率评分 */}
        {efficiency_score !== undefined && (
          <div className="brutal-box p-4 bg-white flex flex-col items-center justify-center text-center">
            <span className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">
              效率评分
            </span>
            <span
              className="text-4xl font-black leading-none"
              style={{ color: scoreColor(efficiency_score) }}
            >
              {efficiency_score}
            </span>
            <span className="text-[10px] font-bold text-gray-400">/ 10 · {scoreLabel(efficiency_score)}</span>
          </div>
        )}

        {/* 整体氛围 */}
        {overall_sentiment && (
          <div className="brutal-box p-4 bg-white flex flex-col items-center justify-center text-center">
            <span className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">
              整体氛围
            </span>
            <span className="text-2xl font-black leading-none">{overall_sentiment}</span>
            {sentiment_score !== undefined && (
              <span className="text-[10px] font-bold text-gray-400 mt-1">
                情绪指数 {(sentiment_score * 100).toFixed(0)}
              </span>
            )}
          </div>
        )}
      </div>

      {/* 发言时长分布 */}
      {sorted.length > 0 && (
        <div className="brutal-box p-4 bg-white">
          <h3 className="text-xs font-black uppercase tracking-widest text-gray-400 border-b-[2px] border-black pb-2 mb-4">
            发言时长分布
          </h3>
          {/* 堆叠色块 */}
          <div className="flex h-3 border-[2px] border-black overflow-hidden mb-4">
            {sorted.map((s, i) => (
              <div
                key={i}
                title={`${s.speaker} ${Math.round(s.speaking_ratio * 100)}%`}
                style={{ width: `${s.speaking_ratio * 100}%`, backgroundColor: getColor(i) }}
              />
            ))}
          </div>
          <div className="space-y-2.5">
            {sorted.map((s, i) => (
              <div key={i}>
                <div className="flex justify-between text-xs font-bold mb-1">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 border border-black flex-shrink-0" style={{ backgroundColor: getColor(i) }} />
                    {s.speaker}
                    {s.segment_count != null && (
                      <span className="text-gray-400 font-normal">({s.segment_count}段)</span>
                    )}
                  </span>
                  <span className="font-black">{Math.round(s.speaking_ratio * 100)}% · {fmtSecs(s.speaking_duration)}</span>
                </div>
                <div className="h-2 bg-gray-100 border-[1.5px] border-black overflow-hidden">
                  <div
                    className="h-full transition-all duration-700"
                    style={{ width: `${s.speaking_ratio * 100}%`, backgroundColor: getColor(i) }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 关键词 */}
      {keywords && keywords.length > 0 && (
        <div className="brutal-box p-4 bg-white">
          <h3 className="text-xs font-black uppercase tracking-widest text-gray-400 border-b-[2px] border-black pb-2 mb-3">
            关键词
          </h3>
          <div className="flex flex-wrap gap-2">
            {keywords.map((kw, i) => (
              <span
                key={i}
                className="text-xs font-black px-2 py-1 border-[2px] border-black shadow-[2px_2px_0px_rgba(0,0,0,1)]"
                style={{ backgroundColor: PALETTE[i % PALETTE.length] + "50" }}
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 亮点 + 改进建议 */}
      {((highlights && highlights.length > 0) || (suggestions && suggestions.length > 0)) && (
        <div className="grid grid-cols-1 gap-3">
          {highlights && highlights.length > 0 && (
            <div className="brutal-box p-4 bg-[#4ade80]/20">
              <h3 className="text-xs font-black uppercase tracking-widest mb-3 border-b-[2px] border-black pb-2">
                亮点
              </h3>
              <ul className="space-y-1.5">
                {highlights.map((h, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span className="font-black flex-shrink-0">+</span>
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {suggestions && suggestions.length > 0 && (
            <div className="brutal-box p-4 bg-[#ffc900]/20">
              <h3 className="text-xs font-black uppercase tracking-widest mb-3 border-b-[2px] border-black pb-2">
                改进建议
              </h3>
              <ul className="space-y-1.5">
                {suggestions.map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span className="font-black flex-shrink-0 text-gray-400">→</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
