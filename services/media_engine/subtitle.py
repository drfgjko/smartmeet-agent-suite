# -*- coding: utf-8 -*-
"""
Subtitle Data Structures & Parsers（字幕数据结构与解析器）
- 结构化存储字幕分片与完整转录内容
- 提供标准 SRT 字幕格式的读取、导出与时间戳转换
- 支持 HTML 标签剥离及防 BOM 头处理
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str

    @property
    def start_ts(self) -> str:
        return _seconds_to_ts(self.start)

    @property
    def end_ts(self) -> str:
        return _seconds_to_ts(self.end)

@dataclass
class SubtitleResult:
    segments: list[SubtitleSegment]
    source: str
    language: str = "zh"
    raw_text: str = ""

    @property
    def full_text(self) -> str:
        if self.raw_text:
            return self.raw_text
        return "\n".join(s.text for s in self.segments)

    @property
    def duration(self) -> float:
        if not self.segments:
            return 0
        return self.segments[-1].end

    @property
    def srt_content(self) -> str:
        lines = []
        for i, seg in enumerate(self.segments, 1):
            lines.append(str(i))
            lines.append(f"{seg.start_ts} --> {seg.end_ts}")
            lines.append(seg.text)
            lines.append("")
        return "\n".join(lines)

    def save_srt(self, path: Path) -> None:
        path.write_text(self.srt_content, encoding="utf-8")

    def save_txt(self, path: Path) -> None:
        path.write_text(self.full_text, encoding="utf-8")

def _seconds_to_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def parse_srt(srt_path: Path) -> list[SubtitleSegment]:
    content = srt_path.read_text(encoding="utf-8", errors="replace")
    content = content.replace("\ufeff", "")

    segments: list[SubtitleSegment] = []
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        ts_match = re.search(
            r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})",
            block,
        )
        if not ts_match:
            continue

        start = _ts_to_seconds(ts_match.group(1))
        end = _ts_to_seconds(ts_match.group(2))

        ts_line_idx = next(
            i for i, l in enumerate(lines)
            if "-->" in l
        )
        text = "\n".join(lines[ts_line_idx + 1:]).strip()
        text = re.sub(r"<[^>]+>", "", text)

        if text:
            segments.append(SubtitleSegment(start=start, end=end, text=text))

    return segments

def _ts_to_seconds(ts: str) -> float:
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
