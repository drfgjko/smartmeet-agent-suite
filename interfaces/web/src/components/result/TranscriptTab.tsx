import React, { useEffect, useRef, useState } from "react";

type TranscriptLine = {
  speaker: string;
  timeStr: string;
  seconds: number;
  text: string;
};

type TranscriptTabProps = {
  /** 带说话人标签的原始逐字稿，格式：
   * "Speaker X [HH:MM:SS]: 文本\n..."
   */
  diarizedTranscript: string;
  /** 当前音频播放时间（秒），用于自动高亮当前行 */
  currentAudioTime: number;
  /** 点击时间戳时触发，跳转音频到指定秒数 */
  onSeek: (seconds: number) => void;
};

/** "HH:MM:SS" 或 "MM:SS" → 秒数 */
function parseTimeStr(t: string): number {
  const parts = t.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

/** 解析逐字稿原始字符串为结构化行数组 */
function parseTranscript(raw: string): TranscriptLine[] {
  if (!raw?.trim()) return [];
  // 匹配：Speaker X [00:00:05]: 文本
  const lineRe = /^(.+?)\s+\[(\d{1,2}:\d{2}(?::\d{2})?)\]:\s*(.+)$/;
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const m = line.match(lineRe);
      if (m) {
        return {
          speaker: m[1].trim(),
          timeStr: m[2].trim(),
          seconds: parseTimeStr(m[2].trim()),
          text: m[3].trim(),
        };
      }
      // 无法解析的行：原样展示，无时间戳联动
      return { speaker: "", timeStr: "", seconds: -1, text: line };
    });
}

/** 从发言人名称生成固定颜色 */
const SPEAKER_COLORS = [
  "#ff90e8", "#ffc900", "#22d3ee", "#c084fc",
  "#4ade80", "#f87171", "#fb923c", "#818cf8",
];
const speakerColorMap = new Map<string, string>();
function getSpeakerColor(speaker: string): string {
  if (!speakerColorMap.has(speaker)) {
    speakerColorMap.set(speaker, SPEAKER_COLORS[speakerColorMap.size % SPEAKER_COLORS.length]);
  }
  return speakerColorMap.get(speaker)!;
}

export default function TranscriptTab({
  diarizedTranscript,
  currentAudioTime,
  onSeek,
}: TranscriptTabProps) {
  const lines = parseTranscript(diarizedTranscript);
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeIdx, setActiveIdx] = useState(-1);

  // 根据当前音频时间计算高亮行并自动滚动
  useEffect(() => {
    if (lines.length === 0 || currentAudioTime < 0) return;
    let idx = -1;
    for (let i = lines.length - 1; i >= 0; i--) {
      if (lines[i].seconds >= 0 && currentAudioTime >= lines[i].seconds) {
        idx = i;
        break;
      }
    }
    if (idx !== activeIdx) {
      setActiveIdx(idx);
      // 自动滚动高亮行到可视区域
      if (idx >= 0 && containerRef.current) {
        const el = containerRef.current.querySelector<HTMLElement>(
          `[data-line="${idx}"]`
        );
        el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  }, [currentAudioTime, lines, activeIdx]);

  if (lines.length === 0) {
    return (
      <p className="text-xs font-bold text-gray-400 text-center py-12">
        暂无逐字稿数据
      </p>
    );
  }

  return (
    <div
      ref={containerRef}
      className="space-y-1 max-h-[calc(100vh-200px)] overflow-y-auto pr-1"
    >
      {lines.map((line, i) => {
        const isActive = i === activeIdx;
        const color = line.speaker ? getSpeakerColor(line.speaker) : "#e5e5e5";

        return (
          <div
            key={i}
            data-line={i}
            className={`group flex gap-3 px-3 py-2 rounded transition-colors duration-150
              ${isActive ? "bg-[#ffc900]/20 border-l-[3px] border-[#ffc900]" : "hover:bg-black/5 border-l-[3px] border-transparent"}`}
          >
            {/* 说话人标签 */}
            {line.speaker && (
              <div className="flex-shrink-0 w-[95px] text-right">
                <span
                  className="text-xs font-black px-1.5 py-0.5 border-[1.5px] border-black"
                  style={{ backgroundColor: color }}
                >
                  {line.speaker.length > 9 ? line.speaker.slice(0, 9) + "…" : line.speaker}
                </span>
              </div>
            )}

            {/* 主体：时间戳 + 文本 */}
            <div className="flex-1 min-w-0">
              {line.seconds >= 0 && (
                <button
                  onClick={() => onSeek(line.seconds)}
                  id={`transcript-seek-${i}`}
                  className="text-xs font-black text-gray-400 font-mono
                    hover:text-black hover:bg-[#ffc900] px-1 py-0.5 mr-2
                    transition-colors border border-transparent hover:border-black"
                  title={`跳转到 ${line.timeStr}`}
                >
                  {line.timeStr}
                </button>
              )}
              <span className={`text-sm leading-relaxed ${isActive ? "font-bold" : ""}`}>
                {line.text}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
