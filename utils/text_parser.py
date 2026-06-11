# -*- coding: utf-8 -*-
"""
纯文本解析工具集合
"""
import re
from typing import Any
from pathlib import Path
from engines.media import DiarizationResult, DiarizedSegment


def parse_transcript_file(path: Path) -> DiarizationResult:
    """
    解析外部传入的带发音人的纯文本对话文件，转换为 DiarizationResult 对象
    """
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")
    segments = []
    speakers = set()
    full_text_parts = []
    
    current_speaker = "Speaker 1"
    current_time_s = 0.0
    
    # 匹配 **Speaker 1** (00:00:00):
    pattern_header = re.compile(r"^\*\*(.*?)\*\*\s*\((\d+:\d+(?::\d+)?)\):")
    # 匹配 [Speaker 1] (00:00:00): 大家好
    pattern_bracket = re.compile(r"^\[(.*?)\]\s*\((\d+:\d+(?::\d+)?)\):\s*(.*)$")
    # 匹配 Speaker 1: 大家好
    pattern_colon = re.compile(r"^([^:\*]+):\s*(.*)$")
    
    def _parse_time(ts_str: str) -> float:
        parts = ts_str.split(":")
        try:
            if len(parts) == 3:
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        except ValueError:
            pass
        return 0.0

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        
        # 1. 匹配标准段落头: **Speaker 1** (00:00:00):
        match_h = pattern_header.match(line_strip)
        if match_h:
            current_speaker = match_h.group(1).strip()
            current_time_s = _parse_time(match_h.group(2))
            speakers.add(current_speaker)
            continue
            
        # 2. 匹配中括号带时间戳: [Speaker 1] (00:00:00): 大家好
        match_b = pattern_bracket.match(line_strip)
        if match_b:
            spk = match_b.group(1).strip()
            ts = _parse_time(match_b.group(2))
            text = match_b.group(3).strip()
            speakers.add(spk)
            segments.append(DiarizedSegment(
                start=ts,
                end=ts + 5.0,
                text=text,
                speaker=spk
            ))
            full_text_parts.append(text)
            continue
            
        # 3. 匹配冒号分割: Speaker 1: 大家好
        match_c = pattern_colon.match(line_strip)
        if match_c:
            spk = match_c.group(1).strip()
            text = match_c.group(2).strip()
            if not spk.lower().startswith("http") and len(spk) < 30:
                speakers.add(spk)
                segments.append(DiarizedSegment(
                    start=current_time_s,
                    end=current_time_s + 5.0,
                    text=text,
                    speaker=spk
                ))
                full_text_parts.append(text)
                current_time_s += 5.0
                continue
        
        # 4. 普通缩进行或普通行
        text = line_strip
        segments.append(DiarizedSegment(
            start=current_time_s,
            end=current_time_s + 5.0,
            text=text,
            speaker=current_speaker
        ))
        full_text_parts.append(text)
        current_time_s += 5.0

    speakers.add(current_speaker)
    return DiarizationResult(
        segments=segments,
        num_speakers=len(speakers) or 1,
        speakers=sorted(list(speakers)) or ["Speaker 1"],
        language="zh",
    )


def create_fallback_diarization(transcript: Any, language: str) -> DiarizationResult:
    """当转录为空或无法进行声纹分离时，创建默认的单说话人分离结果。"""
    return DiarizationResult(
        segments=[
            DiarizedSegment(segment.start, segment.end, segment.text, "Speaker 1")
            for segment in transcript.segments
        ],
        num_speakers=1,
        speakers=["Speaker 1"],
        language=language,
    )
