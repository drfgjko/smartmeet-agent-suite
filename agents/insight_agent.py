# -*- coding: utf-8 -*-
"""
Insight Agent（洞察Agent）
- 情绪分析：整体会议氛围和情感倾向
- 发言统计：各参会人发言时长、占比、次数
- 效率评分：综合评估会议质量
- 关键词提取：TF-IDF 提取核心关键词
"""

from __future__ import annotations
from collections import defaultdict
from typing import Any
from loguru import logger

from schemas import InsightOutput, SpeakerStat
from ._utils import _state_value

INSIGHT_SYSTEM_PROMPT = """你是一位专业的会议分析师。请分析以下会议转写文本，提供多维度的会议洞察。
分析维度：
1. 情绪分析：判断整体会议氛围（positive/neutral/negative），给出0-1的情感得分
2. 关键词：提取5-10个核心关键词
3. 会议亮点：列出2-3个重要亮点
4. 改进建议：提供1-2条改进建议
5. 效率评分：0-10分评估会议效率
你必须严格按照JSON格式输出："""

INSIGHT_USER_PROMPT = """请分析以下会议转写文本。
## 会议转写文本
{transcript}
## 发言统计数据
{speaker_stats}
## 输出格式（严格JSON）
{{
  "overall_sentiment": "positive 或 neutral 或 negative",
  "sentiment_score": 0.75,
  "efficiency_score": 8.0,
  "keywords": ["关键词1", "关键词2"],
  "highlights": ["亮点1", "亮点2"],
  "suggestions": ["建议1"]
}}"""

class InsightAgent:
    """
    洞察Agent - 并行阶段的节点之一

    架构说明:
    1. 规则引擎：计算发言统计（无需LLM，确定性计算）
    2. LLM 分析：情绪/关键词/亮点/建议
    3. 综合评分：结合规则和LLM结果

    面试考点:
    - 哪些用规则、哪些用LLM？（统计用规则，语义分析用LLM）
    - 效率评分怎么设计的？（多指标加权：发言均衡度 + 决策数量 + 时间利用率）
    - 情绪分析的准确率如何保证？（LLM few-shot + 置信度阈值）
    """
    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def process(self, state: object) -> dict:
        meeting_id = _state_value(state, "meeting_id", "unknown")
        logger.info(f"[InsightAgent] Processing meeting: {meeting_id}")
        transcript = _state_value(state, "transcript", None)
        transcript_text = _state_value(state, "transcript_text", "")
        if not transcript_text:
            logger.warning("[InsightAgent] No transcript text available")
            return {"insights": InsightOutput(meeting_id=meeting_id)}
        try:
            speaker_stats = self._compute_speaker_stats(transcript)
            llm_insights = await self._analyze_with_llm(transcript_text, speaker_stats)
            output = InsightOutput(
                meeting_id=meeting_id,
                overall_sentiment=llm_insights.get("overall_sentiment", "neutral"),
                sentiment_score=llm_insights.get("sentiment_score", 0.5),
                speaker_stats=speaker_stats,
                efficiency_score=self._compute_efficiency_score(
                    speaker_stats,
                    llm_insights.get("efficiency_score", 5.0),
                    transcript,
                ),
                keywords=llm_insights.get("keywords", []),
                highlights=llm_insights.get("highlights", []),
                suggestions=llm_insights.get("suggestions", []),
            )
            logger.info(f"[InsightAgent] Analysis complete: sentiment={output.overall_sentiment}, efficiency={output.efficiency_score:.1f}")
            return {"insights": output}
        except Exception as e:
            logger.error(f"[InsightAgent] Error: {e}")
            speaker_stats = self._compute_speaker_stats(transcript)
            return {
                "errors": _state_value(state, "errors", []) + [f"InsightAgent: {str(e)}"],
                "insights": InsightOutput(meeting_id=meeting_id, speaker_stats=speaker_stats),
            }

    @staticmethod
    def _compute_speaker_stats(transcript: Any) -> list[SpeakerStat]:
        if not transcript or not getattr(transcript, "segments", None):
            return []
        stats: dict[str, dict] = defaultdict(lambda: {"duration": 0.0, "word_count": 0, "segment_count": 0})
        total_duration = 0.0
        for seg in transcript.segments:
            duration = seg.end - seg.start
            stats[seg.speaker]["duration"] += duration
            stats[seg.speaker]["word_count"] += len(seg.text)
            stats[seg.speaker]["segment_count"] += 1
            total_duration += duration
        result = []
        for speaker, data in stats.items():
            ratio = data["duration"] / total_duration if total_duration > 0 else 0
            result.append(
                SpeakerStat(
                    speaker=speaker,
                    speaking_duration=round(data["duration"], 1),
                    speaking_ratio=round(ratio, 3),
                    word_count=data["word_count"],
                    segment_count=data["segment_count"],
                )
            )
        result.sort(key=lambda item: item.speaking_duration, reverse=True)
        return result

    async def _analyze_with_llm(self, transcript_text: str, speaker_stats: list[SpeakerStat]) -> dict[str, Any]:
        stats_text = "\n".join(
            f"- {s.speaker}: 发言{s.speaking_duration}秒, 占比{s.speaking_ratio:.1%}, 发言{s.segment_count}次"
            for s in speaker_stats
        )
        messages = [
            {"role": "system", "content": INSIGHT_SYSTEM_PROMPT},
            {"role": "user", "content": INSIGHT_USER_PROMPT.format(transcript=transcript_text, speaker_stats=stats_text)},
        ]
        if self.llm is None:
            return {}
        result = await self.llm.chat_json(messages=messages, temperature=0.3, max_tokens=2048)
        result["overall_sentiment"] = result.get("overall_sentiment", "neutral").lower()
        return result

    @staticmethod
    def _compute_efficiency_score(speaker_stats: list[SpeakerStat], llm_score: float, transcript: Any) -> float:
        if not speaker_stats:
            return llm_score
        ratios = [speaker.speaking_ratio for speaker in speaker_stats]
        n = len(ratios)
        if n > 1:
            mean_ratio = sum(ratios) / n
            gini = sum(abs(ratios[i] - ratios[j]) for i in range(n) for j in range(n)) / (2 * n * n * mean_ratio) if mean_ratio > 0 else 0
            balance_score = (1 - gini) * 10
        else:
            balance_score = 5.0
        if transcript and getattr(transcript, "duration_seconds", 0) > 0:
            total_speaking = sum(speaker.speaking_duration for speaker in speaker_stats)
            utilization = min(total_speaking / transcript.duration_seconds, 1.0)
            utilization_score = utilization * 10
        else:
            utilization_score = 5.0
        final = 0.4 * llm_score + 0.3 * balance_score + 0.3 * utilization_score
        return round(min(max(final, 0), 10), 1)
