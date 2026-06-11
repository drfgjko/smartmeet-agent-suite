# -*- coding: utf-8 -*-
"""
Speaker Diarization Engine（说话人声纹分割引擎）
- 基于 pyannote/speaker-diarization 3.1 识别发言人标记
- 自动和手动音轨声纹比对，计算重合区间比例对齐转录文本
- 自适应相邻同一发言人语段合并，消除碎片化展示
- 优雅降级机制：如果声纹分割不可用，自动退化为全时间段单发言人模板，防止程序崩溃
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from loguru import logger

from .subtitle import SubtitleSegment, SubtitleResult

@dataclass
class DiarizedSegment:
    start: float
    end: float
    text: str
    speaker: str = ""
    confidence: float = 0.0

    @property
    def start_ts(self) -> str:
        return _format_ts(self.start)

    @property
    def end_ts(self) -> str:
        return _format_ts(self.end)

@dataclass
class DiarizationResult:
    segments: list[DiarizedSegment]
    num_speakers: int = 0
    speakers: list[str] | None = None
    language: str = "zh"

    @property
    def duration_seconds(self) -> float:
        if not self.segments:
            return 0.0
        return self.segments[-1].end

    @property
    def full_text(self) -> str:
        lines = []
        for seg in self.segments:
            speaker = seg.speaker or "Unknown"
            lines.append(f"[{speaker}] ({seg.start_ts}): {seg.text}")
        return "\n".join(lines)

    @property
    def transcript_with_speakers(self) -> str:
        # 严格遵守前端 TranscriptTab.tsx 的解析正则：
        # /^(.+?)\s+\[(\d{1,2}:\d{2}(?::\d{2})?)\]:\s*(.+)$/
        # 例如: "Speaker 1 [00:00:00]: 这是一句话。"
        lines = []
        for seg in self.segments:
            speaker = seg.speaker or "Unknown"
            # 确保文本内没有换行符，否则会破坏前端基于行的正则解析导致解析断层
            clean_text = seg.text.replace("\n", " ").strip()
            if clean_text:
                lines.append(f"{speaker} [{seg.start_ts}]: {clean_text}")
        return "\n".join(lines)

def _format_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def diarize(
    audio_path: Path,
    transcript: SubtitleResult | None = None,
    num_speakers: int | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> DiarizationResult:
    # 如果转录结果中已经自带了发言人信息（例如 FunASR 本地提取的声纹），则直接构造并返回
    if transcript and transcript.segments and any(getattr(seg, "speaker", None) is not None for seg in transcript.segments):
        logger.info("转录结果中已包含说话人信息，跳过 PyAnnote 声纹分割。")
        segments = []
        speakers = set()
        for seg in transcript.segments:
            spk = seg.speaker or "Speaker 1"
            segments.append(DiarizedSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                speaker=spk,
            ))
            speakers.add(spk)
        
        # 按照声纹段合并相邻的同一发言人段落
        segments = _merge_adjacent_speakers(segments)
        
        return DiarizationResult(
            segments=segments,
            num_speakers=len(speakers),
            speakers=sorted(list(speakers)),
            language=transcript.language or "zh",
        )

    try:
        return _diarize_pyannote(
            audio_path, transcript, num_speakers, min_speakers, max_speakers
        )
    except ImportError:
        logger.warning("未安装 pyannote-audio，将使用简易的全程单说话人模式")
        return _diarize_simple(audio_path, transcript)
    except Exception as e:
        logger.warning(f"PyAnnote 声纹分割失败: {e}，将使用简易退级模式")
        return _diarize_simple(audio_path, transcript)

def _diarize_pyannote(
    audio_path: Path,
    transcript: SubtitleResult | None,
    num_speakers: int | None,
    min_speakers: int | None,
    max_speakers: int | None,
) -> DiarizationResult:
    from pyannote.audio import Pipeline
    import torch

    hf_token = _get_hf_token()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=hf_token,
    )
    pipeline.to(device)

    diarize_kwargs = {}
    if num_speakers is not None:
        diarize_kwargs["num_speakers"] = num_speakers
    if min_speakers is not None:
        diarize_kwargs["min_speakers"] = min_speakers
    if max_speakers is not None:
        diarize_kwargs["max_speakers"] = max_speakers

    diarization = pipeline(str(audio_path), **diarize_kwargs)

    speaker_turns = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speaker_turns.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker,
        })

    speakers = sorted(set(t["speaker"] for t in speaker_turns))
    speaker_map = {s: f"Speaker {i+1}" for i, s in enumerate(speakers)}

    if transcript and transcript.segments:
        segments = _align_transcript_with_speakers(
            transcript.segments, speaker_turns, speaker_map
        )
    else:
        segments = [
            DiarizedSegment(
                start=t["start"],
                end=t["end"],
                text="",
                speaker=speaker_map.get(t["speaker"], t["speaker"]),
            )
            for t in speaker_turns
        ]

    segments = _merge_adjacent_speakers(segments)

    return DiarizationResult(
        segments=segments,
        num_speakers=len(speakers),
        speakers=list(speaker_map.values()),
        language=transcript.language if transcript else "zh",
    )

def _diarize_simple(
    audio_path: Path,
    transcript: SubtitleResult | None,
) -> DiarizationResult:
    segments = []
    if transcript and transcript.segments:
        for seg in transcript.segments:
            segments.append(DiarizedSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                speaker="Speaker 1",
            ))
    return DiarizationResult(
        segments=segments,
        num_speakers=1,
        speakers=["Speaker 1"],
        language=transcript.language if transcript else "zh",
    )

def _align_transcript_with_speakers(
    transcript_segments: list[SubtitleSegment],
    speaker_turns: list[dict],
    speaker_map: dict[str, str],
) -> list[DiarizedSegment]:
    results = []
    for seg in transcript_segments:
        best_speaker = "Unknown"
        best_overlap = 0.0

        for turn in speaker_turns:
            overlap_start = max(seg.start, turn["start"])
            overlap_end = min(seg.end, turn["end"])
            overlap = max(0, overlap_end - overlap_start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker_map.get(turn["speaker"], turn["speaker"])

        results.append(DiarizedSegment(
            start=seg.start,
            end=seg.end,
            text=seg.text,
            speaker=best_speaker,
        ))

    return results

def _merge_adjacent_speakers(
    segments: list[DiarizedSegment],
    max_gap: float = 1.0,
) -> list[DiarizedSegment]:
    if not segments:
        return segments

    merged = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        
        # 判断上一段是否以完整句号/叹号等结尾
        is_sentence_end = bool(prev.text and prev.text.strip()[-1:] in "。！？.!?")
        
        # 持续时间
        duration_so_far = seg.end - prev.start
        
        # 智能合并策略：
        # 1. 说话人必须相同，且间隔不能太长
        # 2. 如果已经超过 10 秒，并且刚好是一个句子的结尾，则自然切断（软限制）
        # 3. 如果极端情况下超过 30 秒都没有句号，才强制切断（硬限制）
        same_speaker = (seg.speaker == prev.speaker)
        short_gap = (seg.start - prev.end <= max_gap)
        
        should_merge = False
        if same_speaker and short_gap:
            if duration_so_far > 30.0:
                should_merge = False
            elif duration_so_far > 10.0 and is_sentence_end:
                should_merge = False
            else:
                should_merge = True

        if should_merge and prev.text and seg.text:
            merged[-1] = DiarizedSegment(
                start=prev.start,
                end=seg.end,
                text=f"{prev.text} {seg.text}".strip(),
                speaker=prev.speaker,
            )
        else:
            merged.append(seg)

    return merged

def _get_hf_token() -> str | None:
    return (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or None
    )
