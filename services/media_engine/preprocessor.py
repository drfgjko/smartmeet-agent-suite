# -*- coding: utf-8 -*-
"""
Media Preprocessor（媒体预处理器）
- 支持多种音视频格式检测与过滤
- 音频提取与 ASR 友好的 WAV 格式转码 (16kHz, 单声道, PCM 16bit)
- 多媒体文件自动合并与时间戳修正
- 基于 noisereduce 和 DeepFilterNet 的多级音频降噪及 FFmpeg 优雅降维兜底
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

SUPPORTED_VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".ts", ".m4v"}
SUPPORTED_AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".wma", ".opus"}
ALL_MEDIA_EXTS = SUPPORTED_VIDEO_EXTS | SUPPORTED_AUDIO_EXTS

@dataclass
class MergeSegment:
    file_path: str
    start_offset: float
    duration: float

@dataclass
class PreprocessResult:
    audio_path: Path
    original_files: list[Path]
    merge_segments: list[MergeSegment] = field(default_factory=list)
    is_video: bool = False
    video_path: Path | None = None
    duration: float = 0.0
    sample_rate: int = 16000
    denoised: bool = False

def detect_media_type(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    if ext in SUPPORTED_VIDEO_EXTS:
        return "video"
    if ext in SUPPORTED_AUDIO_EXTS:
        return "audio"
    return "unknown"

def get_duration(file_path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0

def extract_audio(
    input_path: Path,
    output_path: Path,
    sample_rate: int = 16000,
    mono: bool = True,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
    ]
    if mono:
        cmd += ["-ac", "1"]
    cmd.append(str(output_path))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr[:500]}")
    if not output_path.exists():
        raise FileNotFoundError(f"Output audio not created: {output_path}")
    return output_path

def merge_files(
    file_paths: list[Path],
    output_path: Path,
) -> tuple[Path, list[MergeSegment]]:
    if len(file_paths) == 1:
        seg = MergeSegment(
            file_path=str(file_paths[0]),
            start_offset=0.0,
            duration=get_duration(file_paths[0]),
        )
        return file_paths[0], [seg]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    segments: list[MergeSegment] = []
    offset = 0.0

    first_ext = file_paths[0].suffix.lower()
    all_same_format = all(f.suffix.lower() == first_ext for f in file_paths)

    if all_same_format and first_ext in {".mp4", ".ts", ".mp3", ".wav", ".flac"}:
        merged, segments = _merge_concat_demuxer(file_paths, output_path)
    else:
        merged, segments = _merge_concat_filter(file_paths, output_path)

    return merged, segments

def _merge_concat_demuxer(
    file_paths: list[Path], output_path: Path
) -> tuple[Path, list[MergeSegment]]:
    list_file = output_path.parent / "concat_list.txt"
    segments: list[MergeSegment] = []
    offset = 0.0

    with open(list_file, "w", encoding="utf-8") as f:
        for fp in file_paths:
            f.write(f"file '{fp.resolve()}'\n")
            dur = get_duration(fp)
            segments.append(MergeSegment(str(fp), offset, dur))
            offset += dur

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    list_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"Merge (demuxer) failed: {result.stderr[:500]}")
    return output_path, segments

def _merge_concat_filter(
    file_paths: list[Path], output_path: Path
) -> tuple[Path, list[MergeSegment]]:
    segments: list[MergeSegment] = []
    offset = 0.0

    inputs = []
    for fp in file_paths:
        inputs += ["-i", str(fp)]
        dur = get_duration(fp)
        segments.append(MergeSegment(str(fp), offset, dur))
        offset += dur

    n = len(file_paths)
    filter_parts = "".join(f"[{i}:a]" for i in range(n))
    filter_complex = f"{filter_parts}concat=n={n}:v=0:a=1[outa]"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex,
        "-map", "[outa]",
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"Merge (filter) failed: {result.stderr[:500]}")
    return output_path, segments

def denoise_audio(
    audio_path: Path,
    output_path: Path | None = None,
    level: int = 1,
) -> Path:
    if level == 0:
        return audio_path

    if output_path is None:
        output_path = audio_path.parent / f"{audio_path.stem}_denoised.wav"

    try:
        import noisereduce as nr
        import numpy as np

        data, sr = _load_wav(audio_path)

        if level == 1:
            reduced = nr.reduce_noise(
                y=data, sr=sr,
                prop_decrease=0.6,
                stationary=True,
            )
        elif level == 2:
            reduced = nr.reduce_noise(
                y=data, sr=sr,
                prop_decrease=0.8,
                stationary=False,
            )
        else:
            reduced = _try_deepfilternet(audio_path, output_path)
            if reduced is not None:
                return reduced
            reduced = nr.reduce_noise(
                y=data, sr=sr,
                prop_decrease=0.95,
                stationary=False,
            )

        _save_wav(output_path, reduced, sr)
        return output_path

    except ImportError:
        if level >= 3:
            result = _try_deepfilternet(audio_path, output_path)
            if result is not None:
                return result
        return _denoise_ffmpeg_fallback(audio_path, output_path, level)

def _try_deepfilternet(audio_path: Path, output_path: Path) -> Path | None:
    try:
        from df.enhance import enhance, init_df
        model, df_state, _ = init_df()
        import torchaudio
        audio, sr = torchaudio.load(str(audio_path))
        enhanced = enhance(model, df_state, audio)
        torchaudio.save(str(output_path), enhanced, sr)
        return output_path
    except (ImportError, Exception):
        return None

def _denoise_ffmpeg_fallback(
    audio_path: Path, output_path: Path, level: int
) -> Path:
    if level == 1:
        af = "highpass=f=80,lowpass=f=8000"
    elif level == 2:
        af = "highpass=f=100,lowpass=f=7000,anlmdn=s=7"
    else:
        af = "highpass=f=120,lowpass=f=6000,anlmdn=s=10,afftdn=nf=-20"

    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-af", af,
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not output_path.exists():
        return audio_path
    return output_path

def _load_wav(path: Path) -> tuple:
    import numpy as np
    import wave

    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        data = wf.readframes(n_frames)
        dtype = np.int16 if wf.getsampwidth() == 2 else np.float32
        arr = np.frombuffer(data, dtype=dtype).astype(np.float32)
        if dtype == np.int16:
            arr = arr / 32768.0
        return arr, sr

def _save_wav(path: Path, data, sr: int):
    import numpy as np
    import wave

    path.parent.mkdir(parents=True, exist_ok=True)
    arr = (data * 32768.0).clip(-32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(arr.tobytes())

def preprocess(
    input_files: list[str | Path],
    work_dir: Path | None = None,
    denoise_level: int = 1,
    progress_callback: Callable[[str, float], None] | None = None,
) -> PreprocessResult:
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="noteking_pre_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    def _progress(step: str, pct: float):
        if progress_callback:
            progress_callback(step, pct)

    paths = [Path(f) for f in input_files]
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        if detect_media_type(p) == "unknown":
            raise ValueError(f"Unsupported file format: {p.suffix}")

    _progress("validate", 0.1)

    is_video = any(detect_media_type(p) == "video" for p in paths)
    video_path = None

    if len(paths) > 1:
        _progress("merge", 0.2)
        merged_ext = ".wav" if not is_video else paths[0].suffix
        merged_path = work_dir / f"merged{merged_ext}"
        merged_path, merge_segments = merge_files(paths, merged_path)
    else:
        merged_path = paths[0]
        merge_segments = [MergeSegment(str(paths[0]), 0.0, get_duration(paths[0]))]

    if is_video:
        video_path = merged_path

    _progress("extract_audio", 0.4)
    audio_path = work_dir / "audio_16k.wav"
    extract_audio(merged_path, audio_path, sample_rate=16000, mono=True)

    _progress("denoise", 0.6)
    if denoise_level > 0:
        denoised_path = work_dir / "audio_denoised.wav"
        audio_path = denoise_audio(audio_path, denoised_path, level=denoise_level)
        denoised = True
    else:
        denoised = False

    duration = get_duration(audio_path)
    _progress("done", 1.0)

    return PreprocessResult(
        audio_path=audio_path,
        original_files=paths,
        merge_segments=merge_segments,
        is_video=is_video,
        video_path=video_path,
        duration=duration,
        sample_rate=16000,
        denoised=denoised,
    )
