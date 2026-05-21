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
    def full_text(self) -> str:
        lines = []
        for seg in self.segments:
            speaker = seg.speaker or "Unknown"
            lines.append(f"[{speaker}] ({seg.start_ts}): {seg.text}")
        return "\n".join(lines)

    @property
    def transcript_with_speakers(self) -> str:
        lines = []
        current_speaker = None
        for seg in self.segments:
            if seg.speaker != current_speaker:
                current_speaker = seg.speaker
                lines.append(f"\n**{current_speaker or 'Unknown'}** ({seg.start_ts}):")
            lines.append(f"  {seg.text}")
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
    try:
        return _diarize_pyannote(
            audio_path, transcript, num_speakers, min_speakers, max_speakers
        )
    except ImportError:
        logger.warning("pyannote-audio not installed, using simple diarization")
        return _diarize_simple(audio_path, transcript)
    except Exception as e:
        logger.warning(f"pyannote diarization failed: {e}, using simple fallback")
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
        if (seg.speaker == prev.speaker
                and seg.start - prev.end <= max_gap
                and prev.text and seg.text):
            merged[-1] = DiarizedSegment(
                start=prev.start,
                end=seg.end,
                text=f"{prev.text} {seg.text}",
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
