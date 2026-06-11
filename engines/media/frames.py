# -*- coding: utf-8 -*-
"""
Smart Keyframe Extractor & Aligner（智能视频关键帧提取与对齐引擎）
- 基于 SceneDetect ContentDetector 进行内容感知型场景边界探测
- 自动进行等距（Uniform）采样补充，填补长时间静态画面空白
- 图像信息密度评估评分机制（边缘梯度、对比度、熵值及颜色独特性）
- 引入感知哈希（Perceptual Hashing, ImageHash）进行相似画面去重
- 语音/字幕时间戳对齐：将画面精确关联到最邻近的发音内容
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from loguru import logger

from .subtitle import SubtitleResult

@dataclass
class ExtractedFrame:
    path: Path
    timestamp: float
    scene_score: float = 0.0
    info_score: float = 0.0
    phash: str = ""
    subtitle_text: str = ""
    caption: str = ""

    @property
    def timestamp_str(self) -> str:
        h = int(self.timestamp // 3600)
        m = int((self.timestamp % 3600) // 60)
        s = int(self.timestamp % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def total_score(self) -> float:
        return self.scene_score * 0.4 + self.info_score * 0.6

def extract_keyframes(
    video_path: Path,
    output_dir: Path,
    max_frames: int = 15,
    interval_seconds: float = 0,
    threshold: float = 25.0,
    dedup: bool = True,
    score: bool = True,
    min_interval: float = 5.0,
) -> list[ExtractedFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    duration = _get_duration(video_path)

    try:
        frames = _extract_with_scenedetect(video_path, output_dir, max_frames * 2, threshold)
    except (ImportError, Exception) as e:
        logger.warning(f"SceneDetect 提取关键帧失败，正在执行降级兜底: {e}")
        frames = []

    if duration > 0:
        if interval_seconds <= 0:
            interval_seconds = max(duration / (max_frames * 1.5), 10)
        _fill_uniform(video_path, output_dir, frames, duration, interval_seconds, min_interval)

    if score:
        _score_info_density(frames)

    if dedup:
        frames = _dedup_by_hash(frames, threshold=8)

    frames = _enforce_interval(frames, min_interval)

    frames.sort(key=lambda f: f.total_score, reverse=True)
    selected = frames[:max_frames]
    selected.sort(key=lambda f: f.timestamp)

    return selected

def _extract_with_scenedetect(
    video_path: Path,
    output_dir: Path,
    max_frames: int,
    threshold: float,
) -> list[ExtractedFrame]:
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector

    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video, show_progress=False)
    scene_list = scene_manager.get_scene_list()

    frames: list[ExtractedFrame] = []
    for i, (start, end) in enumerate(scene_list[:max_frames]):
        t = end.get_seconds() - 0.5
        if t < start.get_seconds():
            t = (start.get_seconds() + end.get_seconds()) / 2
        frame_path = output_dir / f"scene_{i:04d}_{t:.1f}s.jpg"

        _extract_frame_at(video_path, t, frame_path)

        if frame_path.exists() and frame_path.stat().st_size > 3000:
            frames.append(ExtractedFrame(
                path=frame_path,
                timestamp=t,
                scene_score=min(1.0, threshold / 30.0),
            ))

    return frames

def _fill_uniform(
    video_path: Path,
    output_dir: Path,
    existing: list[ExtractedFrame],
    duration: float,
    interval: float,
    min_interval: float,
) -> None:
    t = 3.0
    idx = len(existing)
    while t < duration - 3:
        if any(abs(f.timestamp - t) < min_interval for f in existing):
            t += interval
            continue
        out = output_dir / f"uniform_{idx:04d}_{t:.1f}s.jpg"
        _extract_frame_at(video_path, t, out)
        if out.exists() and out.stat().st_size > 3000:
            existing.append(ExtractedFrame(path=out, timestamp=t, scene_score=0.3))
        idx += 1
        t += interval

def _score_info_density(frames: list[ExtractedFrame]) -> None:
    try:
        from PIL import Image, ImageFilter
        import numpy as np
    except ImportError:
        for f in frames:
            f.info_score = 0.5
        return

    for frame in frames:
        try:
            img = Image.open(frame.path)
            gray = img.convert("L")
            arr = np.array(gray, dtype=np.float32)

            edges = gray.filter(ImageFilter.FIND_EDGES)
            edge_score = min(1.0, np.std(np.array(edges, dtype=np.float32)) / 60.0)

            contrast = min(1.0, np.std(arr) / 80.0)

            hist, _ = np.histogram(arr.ravel(), bins=64, range=(0, 256))
            p = hist / hist.sum()
            p = p[p > 0]
            entropy_score = min(1.0, (-np.sum(p * np.log2(p))) / 6.0)

            unique_ratio = len(np.unique(arr.astype(np.uint8))) / 256.0

            frame.info_score = (
                edge_score * 0.35 + contrast * 0.25 +
                entropy_score * 0.25 + unique_ratio * 0.15
            )
        except Exception:
            frame.info_score = 0.3

def _dedup_by_hash(frames: list[ExtractedFrame], threshold: int = 8) -> list[ExtractedFrame]:
    try:
        import imagehash
        from PIL import Image
    except ImportError:
        return frames

    frames.sort(key=lambda f: f.timestamp)
    unique: list[ExtractedFrame] = []
    seen: list[Any] = []

    for frame in frames:
        try:
            h = imagehash.phash(Image.open(frame.path), hash_size=12)
            frame.phash = str(h)
            if not any(h - prev < threshold for prev in seen):
                seen.append(h)
                unique.append(frame)
        except Exception:
            unique.append(frame)

    return unique

def _enforce_interval(frames: list[ExtractedFrame], min_interval: float) -> list[ExtractedFrame]:
    frames.sort(key=lambda f: f.timestamp)
    filtered = []
    last_t = -999.0
    for f in frames:
        if f.timestamp - last_t >= min_interval:
            filtered.append(f)
            last_t = f.timestamp
        elif f.total_score > 0.7:
            filtered.append(f)
            last_t = f.timestamp
    return filtered

def _extract_frame_at(video_path: Path, timestamp: float, output: Path) -> None:
    cmd = [
        "ffmpeg",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        "-vf", "scale=960:-1",
        str(output),
        "-y", "-loglevel", "error",
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)

def _get_duration(video_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError) as e:
        logger.warning(f"解析 {video_path} 的时长失败: {e}")
        return 0.0

def align_frames_to_subtitles(
    frames: list[ExtractedFrame],
    subtitles: SubtitleResult | list[dict] | list[Any],
    tolerance: float = 10.0,
) -> list[ExtractedFrame]:
    segments = subtitles.segments if isinstance(subtitles, SubtitleResult) else subtitles
    for frame in frames:
        best_text = ""
        best_dist = float("inf")
        for seg in segments:
            seg_start = seg.start if hasattr(seg, "start") else seg.get("start", 0)
            seg_end = seg.end if hasattr(seg, "end") else seg.get("end", 0)
            seg_text = seg.text if hasattr(seg, "text") else seg.get("text", "")
            mid = (seg_start + seg_end) / 2
            dist = abs(frame.timestamp - mid)
            if dist < best_dist and dist <= tolerance:
                best_dist = dist
                best_text = seg_text
        frame.subtitle_text = best_text
    return frames
