# -*- coding: utf-8 -*-
"""
Smartmeet Media Engine
- 预处理、转录、说话人声纹分离与智能关键帧提取、媒体下载接口门面
"""

from .preprocessor import preprocess, PreprocessResult, MergeSegment, get_duration, extract_audio
from .subtitle import SubtitleSegment, SubtitleResult, parse_srt
from .transcriber import transcribe, detect_language
from .diarizer import diarize, DiarizationResult, DiarizedSegment
from .frames import ExtractedFrame, extract_keyframes, align_frames_to_subtitles
from .downloader import VideoMeta, get_video_info, download_subtitles, download_audio, download_video, download_thumbnail, list_playlist_entries

__all__ = [
    "preprocess",
    "PreprocessResult",
    "MergeSegment",
    "get_duration",
    "extract_audio",
    "SubtitleSegment",
    "SubtitleResult",
    "parse_srt",
    "transcribe",
    "detect_language",
    "diarize",
    "DiarizationResult",
    "DiarizedSegment",
    "ExtractedFrame",
    "extract_keyframes",
    "align_frames_to_subtitles",
    "VideoMeta",
    "get_video_info",
    "download_subtitles",
    "download_audio",
    "download_video",
    "download_thumbnail",
    "list_playlist_entries",
]
