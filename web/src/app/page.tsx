"use client";

import { useState, useRef, useCallback } from "react";
import { Result } from "../types";
import UploadPanel from "../components/UploadPanel";
import AudioPlayer, { AudioPlayerHandle } from "../components/result/AudioPlayer";
import MeetingOverview from "../components/result/MeetingOverview";
import SpeakerStats from "../components/result/SpeakerStats";
import ExportActions from "../components/result/ExportActions";

// ─── 开发模式专用 Mock 数据 ───────────────────────────────────────────────────
// 用于绕过真实流水线，直接预览结果页布局。生产构建时此常量不会被使用。
const MOCK_RESULT = {
  meeting_id: "mock-37fe9e7b",
  title: "百年老店人才盘点项目讨论会",
  content: "# 百年老店人才盘点项目讨论会\n\n这是一篇模拟的会议报告正文，用于开发阶段预览布局。",
  source: "file",
  duration: 1843,
  num_speakers: 4,
  speakers: ["Speaker 1", "Speaker 2", "Speaker 3", "Speaker 4"],
  output_files: { markdown: "/mock/report.md" },
  diarized_transcript:
    "Speaker 1 [00:00:05]: 大家好，我们今天来讨论一下人才盘点项目的整体思路。\nSpeaker 2 [00:00:12]: 我认为首先需要明确评估维度和权重。\nSpeaker 3 [00:00:54]: 关于高考志愿动态填报这个项目，我觉得可以作为参考案例。\nSpeaker 4 [00:01:30]: 我补充一下，我们需要确保数据的准确性和一致性。",
  summary: {
    title: "百年老店人才盘点项目讨论会",
    date: "今天",
    participants: ["Speaker 1", "Speaker 2", "Speaker 3", "Speaker 4"],
    topics: [
      {
        title: "项目背景与目标",
        discussion_points: ["明确人才盘点的核心目的", "确定评估维度与权重体系"],
        conclusion: "以能力模型为核心构建评估框架",
      },
      {
        title: "数据采集方案",
        discussion_points: ["线上问卷 + 360 度评估", "HR 系统数据打通"],
        conclusion: "采用混合采集方案，确保数据覆盖度",
      },
    ],
    decisions: ["第一阶段覆盖总部200名核心员工", "11月底前完成数据采集"],
    next_steps: ["设计评估问卷（Speaker 2 负责）", "搭建数据平台（Speaker 4 负责）"],
  },
  actions: {
    action_items: [
      { task: "设计评估问卷", assignee: "Speaker 2", deadline: "2024-11-15", priority: "High" },
      { task: "搭建数据采集平台", assignee: "Speaker 4", deadline: "2024-11-20", priority: "Medium" },
      { task: "与 HR 系统对接", assignee: "Speaker 1", deadline: "2024-11-25", priority: "Medium" },
    ],
  },
  insights: {
    efficiency_score: 8.2,
    overall_sentiment: "积极",
    sentiment_score: 0.82,
    keywords: ["人才盘点", "评估维度", "能力模型", "数据平台", "360度评估", "HR系统"],
    highlights: ["与会者讨论积极，达成多项共识"],
    suggestions: ["建议下次会议提前准备数据样例"],
    speaker_stats: [
      { speaker: "Speaker 1", speaking_duration: 648, speaking_ratio: 0.352, segment_count: 12 },
      { speaker: "Speaker 2", speaking_duration: 387, speaking_ratio: 0.210, segment_count: 8 },
      { speaker: "Speaker 3", speaking_duration: 521, speaking_ratio: 0.283, segment_count: 10 },
      { speaker: "Speaker 4", speaking_duration: 287, speaking_ratio: 0.155, segment_count: 6 },
    ],
  },
};
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://api:8000";

export default function Home() {
  const [result, setResult] = useState<Result | null>(null);
  // 当前音频播放时间，供右侧逐字稿联动（4.2 阶段接入）
  const [currentAudioTime, setCurrentAudioTime] = useState(0);
  const audioPlayerRef = useRef<AudioPlayerHandle>(null);

  const handleUploadSuccess = (r: Result) => {
    setResult(r);
    setCurrentAudioTime(0);
  };

  /** 右侧逐字稿点击时间戳，联动音频跳转（供 4.2 的 TranscriptTab 调用） */
  const handleSeekAudio = useCallback((seconds: number) => {
    audioPlayerRef.current?.seekTo(seconds);
  }, []);

  // 构建音频 URL
  const audioUrl = result?.meeting_id
    ? `${API_BASE}/api/v1/reports/${result.meeting_id}/audio`
    : "";

  // 从 insights.speaker_stats 提取发言人统计数据
  const speakerStats = result?.insights?.speaker_stats ?? [];

  return (
    <div className="w-full h-full flex flex-col">
      {/* ─── 上传 / 结果 状态切换 ─── */}
      {!result ? (
        /* 上传状态 */
        <div className="p-8 max-w-5xl mx-auto w-full">
          <div className="mb-12 border-b-[4px] border-black pb-6 flex items-end justify-between">
            <div>
              <h1 className="text-6xl font-black tracking-tighter">工作台</h1>
              <p className="font-bold text-gray-700 mt-2 text-xl">SMARTMEET 智能中枢</p>
            </div>
            {/* 仅开发环境：快速加载 Mock 数据跳过流水线，用于 UI 调试 */}
            {process.env.NODE_ENV === "development" && (
              <button
                id="dev-load-mock-btn"
                onClick={() => setResult(MOCK_RESULT)}
                className="brutal-btn text-xs bg-[#ffc900] hover:shadow-[6px_6px_0px_rgba(0,0,0,1)] border-dashed"
                title="开发模式：跳过流水线，直接载入 Mock 结果预览布局"
              >
                [DEV] 加载 Mock 数据
              </button>
            )}
          </div>
          <UploadPanel API_BASE={API_BASE} onSuccess={handleUploadSuccess} />
        </div>
      ) : (
        /* 结果状态 — 两栏布局 */
        <div className="flex flex-col h-full overflow-hidden">
          {/* 顶部标题栏 */}
          <div className="flex items-center justify-between px-8 py-4 border-b-[3px] border-black bg-white flex-shrink-0">
            <div>
              <h1 className="text-xl font-black leading-tight truncate max-w-[500px]">
                {result.title}
              </h1>
              <p className="text-xs font-bold text-gray-400 mt-0.5 uppercase tracking-wider">
                会议 ID: {result.meeting_id ?? "—"}
              </p>
            </div>
            <button
              id="result-back-btn"
              onClick={() => setResult(null)}
              className="brutal-btn text-sm bg-white hover:bg-[#ff90e8]"
            >
              开启新任务
            </button>
          </div>

          {/* 两栏主体 */}
          <div className="flex flex-1 overflow-hidden">
            {/* ── 左侧 ~40% ── */}
            <aside className="w-[400px] min-w-[320px] flex-shrink-0 h-full overflow-y-auto border-r-[3px] border-black bg-[#f4f4f0] p-5 space-y-4">
              {/* 音频播放器 */}
              {audioUrl && (
                <AudioPlayer
                  ref={audioPlayerRef}
                  src={audioUrl}
                  onTimeUpdate={setCurrentAudioTime}
                />
              )}

              {/* 会议概览 */}
              <MeetingOverview result={result} />

              {/* 发言人统计 */}
              {speakerStats.length > 0 && (
                <SpeakerStats stats={speakerStats} />
              )}

              {/* 操作区 */}
              <ExportActions result={result} API_BASE={API_BASE} />
            </aside>

            {/* ── 右侧 ~60% — 4.2 阶段接入 Tab 组件 ── */}
            <main className="flex-1 h-full overflow-y-auto p-6 bg-[#f4f4f0]">
              {/* TODO(阶段四 4.2): 替换为 TranscriptTab / SummaryTab / ActionsTab / InsightsTab */}
              <div className="brutal-box p-6 bg-white space-y-3">
                <h2 className="text-sm font-black uppercase tracking-widest text-gray-400 border-b-[2px] border-black pb-2">
                  详情面板
                </h2>
                <p className="text-xs font-bold text-gray-400">
                  Tab 内容区（逐字稿 / 纪要 / 待办 / 洞察）正在 4.2 阶段开发中，即将接入。
                </p>
                {/* 临时展示逐字稿原文 */}
                {result.diarized_transcript && (
                  <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed max-h-[70vh] overflow-y-auto text-gray-700 bg-[#f9f9f6] p-4 border-[2px] border-black">
                    {result.diarized_transcript}
                  </pre>
                )}
              </div>
            </main>
          </div>
        </div>
      )}
    </div>
  );
}
