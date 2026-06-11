# -*- coding: utf-8 -*-
"""media_engine 子模块独立单元测试"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from engines.media import (
    ExtractedFrame,
    Platform,
    LinkType,
    ParsedLink,
    SubtitleSegment,
    SubtitleResult,
    DiarizedSegment,
    DiarizationResult,
    detect_media_type,
    parse_link,
    parse_srt,
)
from engines.media.diarizer import _merge_adjacent_speakers


class TestParser:
    """parser.py: parse_link / Platform / LinkType"""

    def test_platform_enum_values(self):
        assert Platform.BILIBILI.value == "bilibili"
        assert Platform.YOUTUBE.value == "youtube"
        assert Platform.LOCAL.value == "local"
        assert Platform.UNKNOWN.value == "unknown"

    def test_link_type_enum_values(self):
        assert LinkType.SINGLE.value == "single"
        assert LinkType.PLAYLIST.value == "playlist"
        assert LinkType.LOCAL_FILE.value == "local_file"

    def test_parse_bilibili_single(self):
        result = parse_link("https://www.bilibili.com/video/BV1GJ411x7dQ")
        assert result.platform == Platform.BILIBILI
        assert result.link_type == LinkType.SINGLE
        assert result.video_id == "BV1GJ411x7dQ"

    def test_parse_bilibili_multipart(self):
        result = parse_link("https://www.bilibili.com/video/BV1GJ411x7dQ?p=2")
        assert result.platform == Platform.BILIBILI
        assert result.link_type == LinkType.MULTI_PART

    def test_parse_youtube_single(self):
        result = parse_link("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.platform == Platform.YOUTUBE
        assert result.link_type == LinkType.SINGLE
        assert result.video_id == "dQw4w9WgXcQ"

    def test_parse_youtube_short(self):
        result = parse_link("https://youtu.be/dQw4w9WgXcQ")
        assert result.platform == Platform.YOUTUBE
        assert result.video_id == "dQw4w9WgXcQ"

    def test_parse_youtube_playlist(self):
        url = "https://www.youtube.com/playlist?list=PLA1B2C3D4E5F6G7H8"
        result = parse_link(url)
        assert result.platform == Platform.YOUTUBE
        assert result.link_type == LinkType.PLAYLIST

    def test_parse_local_file(self, tmp_path):
        f = tmp_path / "video.mp4"
        f.write_text("dummy")
        result = parse_link(str(f))
        assert result.platform == Platform.LOCAL
        assert result.link_type == LinkType.LOCAL_FILE

    def test_parse_unknown(self):
        result = parse_link("https://example.com/video")
        assert result.platform == Platform.UNKNOWN
        assert result.link_type == LinkType.SINGLE

    def test_parse_instagram(self):
        result = parse_link("https://www.instagram.com/p/ABC123/")
        assert result.platform == Platform.INSTAGRAM

    def test_parse_tiktok(self):
        result = parse_link("https://www.tiktok.com/@user/video/123")
        assert result.platform == Platform.TIKTOK


class TestSubtitle:
    """subtitle.py: SubtitleSegment, SubtitleResult, parse_srt, timestamps"""

    def test_subtitle_segment_properties(self):
        seg = SubtitleSegment(start=3661.5, end=3662.0, text="Hello")
        assert seg.start_ts == "01:01:01,500"
        assert seg.end_ts == "01:01:02,000"

    def test_subtitle_result_full_text_with_segments(self):
        segs = [
            SubtitleSegment(start=0, end=1, text="Hello"),
            SubtitleSegment(start=1, end=2, text="World"),
        ]
        result = SubtitleResult(segments=segs, source="test")
        assert result.full_text == "Hello\nWorld"

    def test_subtitle_result_full_text_raw(self):
        result = SubtitleResult(segments=[], source="test", raw_text="raw content")
        assert result.full_text == "raw content"

    def test_subtitle_result_duration(self):
        segs = [
            SubtitleSegment(start=0, end=1.5, text="A"),
            SubtitleSegment(start=2, end=5.0, text="B"),
        ]
        result = SubtitleResult(segments=segs, source="test")
        assert result.duration == 5.0

    def test_subtitle_result_empty_duration(self):
        result = SubtitleResult(segments=[], source="test")
        assert result.duration == 0

    def test_srt_content(self):
        segs = [SubtitleSegment(start=1.0, end=2.5, text="Hello")]
        result = SubtitleResult(segments=segs, source="test")
        expected = "1\n00:00:01,000 --> 00:00:02,500\nHello\n"
        assert result.srt_content == expected

    def test_parse_srt_basic(self, tmp_path):
        srt_content = """1
00:00:01,000 --> 00:00:02,500
Hello world

2
00:00:03,000 --> 00:00:04,000
Second line
"""
        srt_file = tmp_path / "test.srt"
        srt_file.write_text(srt_content, encoding="utf-8")
        segments = parse_srt(srt_file)
        assert len(segments) == 2
        assert segments[0].start == 1.0
        assert segments[0].end == 2.5
        assert segments[0].text == "Hello world"
        assert segments[1].start == 3.0
        assert segments[1].text == "Second line"

    def test_parse_srt_with_bom(self, tmp_path):
        content = "\ufeff1\n00:00:01,000 --> 00:00:02,000\nBOM test\n"
        srt_file = tmp_path / "bom.srt"
        srt_file.write_text(content, encoding="utf-8")
        segments = parse_srt(srt_file)
        assert len(segments) == 1
        assert segments[0].text == "BOM test"

    def test_parse_srt_html_tags_stripped(self, tmp_path):
        content = "1\n00:00:01,000 --> 00:00:02,000\n<font color=red>Hello</font>\n"
        srt_file = tmp_path / "html.srt"
        srt_file.write_text(content, encoding="utf-8")
        segments = parse_srt(srt_file)
        assert segments[0].text == "Hello"

    def test_parse_srt_empty(self, tmp_path):
        srt_file = tmp_path / "empty.srt"
        srt_file.write_text("", encoding="utf-8")
        segments = parse_srt(srt_file)
        assert segments == []

    def test_save_and_load_srt(self, tmp_path):
        segs = [
            SubtitleSegment(start=0, end=1, text="First"),
            SubtitleSegment(start=2, end=3, text="Second"),
        ]
        result = SubtitleResult(segments=segs, source="test")
        out = tmp_path / "out.srt"
        result.save_srt(out)
        loaded = parse_srt(out)
        assert len(loaded) == 2
        assert loaded[0].text == "First"
        assert loaded[1].text == "Second"

    def test_save_txt(self, tmp_path):
        segs = [
            SubtitleSegment(start=0, end=1, text="Line1"),
            SubtitleSegment(start=1, end=2, text="Line2"),
        ]
        result = SubtitleResult(segments=segs, source="test")
        out = tmp_path / "out.txt"
        result.save_txt(out)
        assert out.read_text(encoding="utf-8") == "Line1\nLine2"


class TestFrames:
    """frames.py: ExtractedFrame properties"""

    def test_timestamp_str(self):
        frame = ExtractedFrame(path=Path("dummy.jpg"), timestamp=3661.5)
        assert frame.timestamp_str == "01:01:01"

    def test_timestamp_str_zero(self):
        frame = ExtractedFrame(path=Path("dummy.jpg"), timestamp=0)
        assert frame.timestamp_str == "00:00:00"

    def test_timestamp_str_long(self):
        frame = ExtractedFrame(path=Path("dummy.jpg"), timestamp=90061.0)
        assert frame.timestamp_str == "25:01:01"

    def test_total_score_default(self):
        frame = ExtractedFrame(path=Path("dummy.jpg"), timestamp=0)
        assert frame.total_score == 0.0

    def test_total_score_with_scores(self):
        frame = ExtractedFrame(
            path=Path("dummy.jpg"),
            timestamp=0,
            scene_score=0.8,
            info_score=0.6,
        )
        expected = 0.8 * 0.4 + 0.6 * 0.6
        assert frame.total_score == expected


class TestDiarizer:
    """diarizer.py: DiarizedSegment, DiarizationResult, _merge_adjacent_speakers"""

    def test_diarized_segment_start_ts(self):
        seg = DiarizedSegment(start=120.0, end=125.0, text="hello")
        assert seg.start_ts == "00:02:00"

    def test_diarized_segment_end_ts(self):
        seg = DiarizedSegment(start=0, end=3661.0, text="test")
        assert seg.end_ts == "01:01:01"

    def test_diarization_result_full_text(self):
        segs = [
            DiarizedSegment(start=0, end=1, text="Hello", speaker="A"),
            DiarizedSegment(start=1, end=2, text="World", speaker="B"),
        ]
        result = DiarizationResult(segments=segs)
        assert "[A] (00:00:00): Hello" in result.full_text
        assert "[B] (00:00:01): World" in result.full_text

    def test_diarization_result_transcript_with_speakers(self):
        segs = [
            DiarizedSegment(start=0, end=1, text="Hello", speaker="Speaker 1"),
            DiarizedSegment(start=1, end=2, text="World", speaker="Speaker 1"),
            DiarizedSegment(start=2, end=3, text="Hi", speaker="Speaker 2"),
        ]
        result = DiarizationResult(segments=segs)
        output = result.transcript_with_speakers
        assert "Speaker 1 [00:00:00]" in output
        assert "Speaker 2" in output
        assert output.index("Speaker 1") < output.index("Speaker 2")

    def test_diarization_result_empty_full_text(self):
        result = DiarizationResult(segments=[])
        assert result.full_text == ""

    def test_merge_adjacent_speakers_merges_same(self):
        segs = [
            DiarizedSegment(start=0, end=1, text="Hello", speaker="A"),
            DiarizedSegment(start=1.2, end=2, text="World", speaker="A"),
        ]
        merged = _merge_adjacent_speakers(segs)
        assert len(merged) == 1
        assert merged[0].text == "Hello World"

    def test_merge_adjacent_speakers_keeps_different(self):
        segs = [
            DiarizedSegment(start=0, end=1, text="Hello", speaker="A"),
            DiarizedSegment(start=1.2, end=2, text="World", speaker="B"),
        ]
        merged = _merge_adjacent_speakers(segs)
        assert len(merged) == 2

    def test_merge_adjacent_speakers_gap_too_large(self):
        segs = [
            DiarizedSegment(start=0, end=1, text="Hello", speaker="A"),
            DiarizedSegment(start=5, end=6, text="World", speaker="A"),
        ]
        merged = _merge_adjacent_speakers(segs, max_gap=1.0)
        assert len(merged) == 2

    def test_merge_adjacent_speakers_empty(self):
        assert _merge_adjacent_speakers([]) == []

    def test_merge_adjacent_speakers_single(self):
        segs = [DiarizedSegment(start=0, end=1, text="Hello", speaker="A")]
        merged = _merge_adjacent_speakers(segs)
        assert len(merged) == 1
        assert merged[0].text == "Hello"


class TestPreprocessor:
    """preprocessor.py: detect_media_type"""

    def test_detect_video_extensions(self):
        for ext in [".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".ts", ".m4v"]:
            assert detect_media_type(Path(f"file{ext}")) == "video"

    def test_detect_audio_extensions(self):
        for ext in [".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma", ".opus"]:
            assert detect_media_type(Path(f"file{ext}")) == "audio"

    def test_detect_unknown_extensions(self):
        for ext in [".txt", ".pdf", ".jpg", ".srt", ""]:
            assert detect_media_type(Path(f"file{ext}")) == "unknown"

    def test_detect_case_insensitive(self):
        assert detect_media_type(Path("file.MP4")) == "video"
        assert detect_media_type(Path("file.WAV")) == "audio"