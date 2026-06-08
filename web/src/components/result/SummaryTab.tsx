import React from "react";

type Topic = {
  title: string;
  discussion_points?: string[];
  conclusion?: string;
  participants?: string[];
};

type SummaryData = {
  title?: string;
  date?: string;
  participants?: string[];
  topics?: Topic[];
  decisions?: string[];
  next_steps?: string[];
};

type SummaryTabProps = {
  summary: SummaryData;
};

export default function SummaryTab({ summary }: SummaryTabProps) {
  if (!summary) {
    return (
      <p className="text-xs font-bold text-gray-400 text-center py-12">
        暂无纪要数据
      </p>
    );
  }

  const { date, participants, topics, decisions, next_steps } = summary;

  return (
    <div className="space-y-5">
      {/* 元信息 */}
      {(date || (participants && participants.length > 0)) && (
        <div className="flex flex-wrap gap-3 text-xs font-bold">
          {date && (
            <span className="px-2 py-1 border-[2px] border-black bg-[#f4f4f0] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              日期：{date}
            </span>
          )}
          {participants && participants.length > 0 && (
            <span className="px-2 py-1 border-[2px] border-black bg-[#f4f4f0] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              参会：{participants.join(" · ")}
            </span>
          )}
        </div>
      )}

      {/* 议题列表 */}
      {topics && topics.length > 0 && (
        <div className="space-y-4">
          {topics.map((topic, i) => (
            <div
              key={i}
              className="brutal-box p-4 bg-white"
            >
              {/* 议题标题 */}
              <div className="flex items-center gap-2 mb-3 border-b-[2px] border-black pb-2">
                <span className="w-6 h-6 flex items-center justify-center font-black text-xs bg-black text-white flex-shrink-0">
                  {i + 1}
                </span>
                <h3 className="font-black text-sm">{topic.title}</h3>
              </div>

              {/* 讨论要点 */}
              {topic.discussion_points && topic.discussion_points.length > 0 && (
                <ul className="space-y-1.5 mb-3">
                  {topic.discussion_points.map((pt, j) => (
                    <li key={j} className="flex gap-2 text-sm">
                      <span className="flex-shrink-0 mt-1 w-1.5 h-1.5 bg-black rounded-full" />
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>
              )}

              {/* 结论 */}
              {topic.conclusion && (
                <div className="flex gap-2 items-start bg-[#4ade80]/20 border-[2px] border-black px-3 py-2 shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                  <span className="text-xs font-black flex-shrink-0 mt-0.5">结论</span>
                  <span className="text-sm font-bold">{topic.conclusion}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 会议决策 */}
      {decisions && decisions.length > 0 && (
        <div className="brutal-box p-4 bg-[#ffc900]">
          <h3 className="text-xs font-black uppercase tracking-widest mb-3 border-b-[2px] border-black pb-2">
            会议决策
          </h3>
          <ul className="space-y-2">
            {decisions.map((d, i) => (
              <li key={i} className="flex gap-2 text-sm font-bold">
                <span className="flex-shrink-0 font-black">#{i + 1}</span>
                <span>{d}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 下一步计划 */}
      {next_steps && next_steps.length > 0 && (
        <div className="brutal-box p-4 bg-[#22d3ee]/20">
          <h3 className="text-xs font-black uppercase tracking-widest mb-3 border-b-[2px] border-black pb-2">
            下一步计划
          </h3>
          <ul className="space-y-2">
            {next_steps.map((s, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="flex-shrink-0 text-gray-400 font-bold">{i + 1}.</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
