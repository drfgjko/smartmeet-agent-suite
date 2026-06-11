# -*- coding: utf-8 -*-
"""
Media Download Engine（媒体下载引擎）
- 封装 yt-dlp 命令行工具，支持流式下载和音视频分离
- 自动适配网络代理 (HTTP/SOCKS5) 及 Bilibili 登录 Cookie (SESSDATA) 防反爬
- 支持单个视频与播放列表批量解析及元数据反序列化
- 本地高速缓冲，断点续传支持
"""

from __future__ import annotations

import os
import json
import platform
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

@dataclass
class VideoMeta:
    title: str = ""
    description: str = ""
    duration: float = 0.0
    uploader: str = ""
    upload_date: str = ""
    thumbnail: str = ""
    webpage_url: str = ""
    chapters: list[dict] = field(default_factory=list)
    subtitles: dict = field(default_factory=dict)
    entries: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def has_subtitles(self) -> bool:
        return bool(self.subtitles)

    @property
    def is_playlist(self) -> bool:
        return bool(self.entries)

    @property
    def entry_count(self) -> int:
        return len(self.entries) if self.entries else 1

_BILIBILI_COOKIES_PATH = "/app/bilibili_cookies.txt"
if platform.system() == "Windows":
    _BILIBILI_COOKIES_PATH = str(Path(os.environ.get("LOCALAPPDATA", "")) / "smartmeet" / "bilibili_cookies.txt")
BILIBILI_COOKIES_FILE = Path(_BILIBILI_COOKIES_PATH)

def _base_cmd(url: str = "") -> list[str]:
    cmd = ["yt-dlp", "--verbose", "--proxy", ""]

    # 哔哩哔哩不需要代理，而且如果系统的本地代理服务没开或者拦截了，会导致 [WinError 10061] 连接被拒
    is_bilibili = "bilibili.com" in url or "b23.tv" in url

    if not is_bilibili:
        proxy = os.environ.get("NOTEKING_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("SOCKS5_PROXY")
        if proxy:
            cmd += ["--proxy", proxy]

    if BILIBILI_COOKIES_FILE.exists():
        cmd += ["--cookies", str(BILIBILI_COOKIES_FILE)]
    else:
        sessdata = os.environ.get("BILIBILI_SESSDATA", "")
        if sessdata and sessdata != "your_sessdata_here":
            # 不要使用 unquote() 解码！B 站的 Cookie 包含逗号等特殊字符，
            # 如果解码后放入 Cookie 文件，会导致 yt-dlp 发送非法的 HTTP Cookie 请求头（包含明文逗号），
            # 这会触发 B 站 WAF 防火墙的拦截，直接导致 TCP 连接超时 (TimeoutError)！
            from utils.file_system import get_tmp_dir
            tmp = Path(tempfile.mktemp(suffix="_bili_cookies.txt", dir=str(get_tmp_dir())))
            tmp.write_text(
                f"# Netscape HTTP Cookie File\n"
                f".bilibili.com\tTRUE\t/\tTRUE\t2147483647\tSESSDATA\t{sessdata}\n",
                encoding="utf-8"
            )
            cmd += ["--cookies", str(tmp)]

    # 设置标准的浏览器 User-Agent 伪装，避免触发 B 站等平台的自动化爬虫拦截风控 (如 HTTP 412 错误)
    cmd += ["--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"]

    return cmd

def get_video_info(url: str) -> VideoMeta:
    cmd = _base_cmd() + [
        "--dump-json",
        "--flat-playlist",
        "--no-download",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if result.returncode != 0:
        err_msg = (result.stderr or result.stdout or '')[-1000:]
        raise RuntimeError(f"获取媒体元数据失败 (yt-dlp info 失败): {err_msg}")

    lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
    if not lines:
        raise RuntimeError("媒体下载引擎未返回任何数据")

    entries = []
    first = json.loads(lines[0])

    if len(lines) > 1:
        for line in lines:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return VideoMeta(
        title=first.get("title", ""),
        description=first.get("description", ""),
        duration=first.get("duration", 0) or 0,
        uploader=first.get("uploader", ""),
        upload_date=first.get("upload_date", ""),
        thumbnail=first.get("thumbnail", ""),
        webpage_url=first.get("webpage_url", url),
        chapters=first.get("chapters") or [],
        subtitles=first.get("subtitles") or {},
        entries=entries if len(entries) > 1 else [],
        extra={"id": first.get("id", "")},
    )

def download_subtitles(
    url: str,
    output_dir: Path,
    langs: str = "zh-Hans,zh-CN,zh,ai-zh,en",
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = _base_cmd() + [
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs", langs,
        "--convert-subs", "srt",
        "--skip-download",
        "-o", str(output_dir / "%(title)s.%(ext)s"),
        url,
    ]
    subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return list(output_dir.glob("*.srt"))

def download_audio(
    url: str,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "audio.wav"
    cmd = _base_cmd(url) + [
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "-o", str(output_path),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if result.returncode != 0:
        err_msg = f"返回值={result.returncode} | 错误输出={(result.stderr or '').strip()} | 标准输出={(result.stdout or '')[-1000:].strip()}"
        raise RuntimeError(f"音频下载失败: {err_msg}")

    wavs = list(output_dir.glob("*.wav"))
    if wavs:
        return wavs[0]
    raise FileNotFoundError("未生成有效的 WAV 音频文件")

def download_video(
    url: str,
    output_dir: Path,
    quality: str = "",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = _base_cmd(url)
    if quality:
        cmd += ["-f", quality]
    cmd += [
        "-o", str(output_dir / "%(title)s.%(ext)s"),
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    if result.returncode != 0:
        err_msg = f"返回值={result.returncode} | 错误输出={(result.stderr or '').strip()} | 标准输出={(result.stdout or '')[-1000:].strip()}"
        raise RuntimeError(f"视频下载失败: {err_msg}")

    for ext in ("mp4", "mkv", "webm", "flv"):
        vids = list(output_dir.glob(f"*.{ext}"))
        if vids:
            return vids[0]
    raise FileNotFoundError("未生成任何合法的视频文件")

def download_thumbnail(
    url: str,
    output_dir: Path,
) -> Path | None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = _base_cmd() + [
        "--write-thumbnail",
        "--skip-download",
        "--convert-thumbnails", "jpg",
        "-o", str(output_dir / "thumbnail"),
        url,
    ]
    subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    for ext in ("jpg", "png", "webp"):
        thumbs = list(output_dir.glob(f"thumbnail*.{ext}"))
        if thumbs:
            return thumbs[0]
    return None

def list_playlist_entries(url: str) -> list[dict]:
    cmd = _base_cmd() + [
        "--flat-playlist",
        "--dump-json",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    entries = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries
