# -*- coding: utf-8 -*-
"""
Link Parser Module
- 识别音视频 URL 的所属平台与类型（如 Bilibili, YouTube 及其 Video ID）
- 支持本地文件路径的识别与处理
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse, parse_qs

class Platform(str, Enum):
    BILIBILI = "bilibili"
    YOUTUBE = "youtube"
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    KUAISHOU = "kuaishou"
    TIKTOK = "tiktok"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    TWITCH = "twitch"
    VIMEO = "vimeo"
    FACEBOOK = "facebook"
    REDDIT = "reddit"
    PODCAST = "podcast"
    LOCAL = "local"
    UNKNOWN = "unknown"

class LinkType(str, Enum):
    SINGLE = "single"
    PLAYLIST = "playlist"
    SERIES = "series"
    COLLECTION = "collection"
    FAVORITES = "favorites"
    CHANNEL = "channel"
    MULTI_PART = "multi_part"
    LOCAL_FILE = "local_file"

@dataclass
class ParsedLink:
    url: str
    platform: Platform
    link_type: LinkType
    video_id: str = ""
    playlist_id: str = ""
    title: str = ""
    extra: dict = field(default_factory=dict)

# 正则表达式规则
_BILIBILI_PATTERNS = [
    (r"bilibili\.com/video/(BV[\w]+)", LinkType.SINGLE),
    (r"bilibili\.com/video/av(\d+)", LinkType.SINGLE),
    (r"b23\.tv/([\w]+)", LinkType.SINGLE),
    (r"bilibili\.com/list/(\d+)", LinkType.PLAYLIST),
    (r"space\.bilibili\.com/\d+/channel/seriesdetail\?sid=(\d+)", LinkType.SERIES),
    (r"space\.bilibili\.com/\d+/favlist\?fid=(\d+)", LinkType.FAVORITES),
    (r"bilibili\.com/watchlater", LinkType.COLLECTION),
]

_YOUTUBE_PATTERNS = [
    (r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})", LinkType.SINGLE),
    (r"youtube\.com/playlist\?list=([\w-]+)", LinkType.PLAYLIST),
    (r"youtube\.com/(?:c/|channel/|@)([\w-]+)", LinkType.CHANNEL),
]

def _detect_bilibili_multipart(url: str) -> bool:
    """检查 Bilibili 链接是否包含分 P 标识"""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return "p" in qs

def parse_link(url: str) -> ParsedLink:
    """解析 URL 链接或本地文件路径，返回结构化的 ParsedLink 对象"""
    stripped = url.strip()

    # 检查是否为本地文件路径
    if os.path.exists(stripped):
        return ParsedLink(
            url=stripped,
            platform=Platform.LOCAL,
            link_type=LinkType.LOCAL_FILE,
            video_id=os.path.basename(stripped),
        )

    # 检查 Bilibili 规则
    for pattern, link_type in _BILIBILI_PATTERNS:
        m = re.search(pattern, stripped)
        if m:
            vid = m.group(1)
            lt = link_type
            if lt == LinkType.SINGLE and _detect_bilibili_multipart(stripped):
                lt = LinkType.MULTI_PART
            return ParsedLink(
                url=stripped,
                platform=Platform.BILIBILI,
                link_type=lt,
                video_id=vid,
            )

    # 检查 YouTube 规则
    for pattern, link_type in _YOUTUBE_PATTERNS:
        m = re.search(pattern, stripped)
        if m:
            vid = m.group(1)
            extra = {}
            if link_type == LinkType.SINGLE:
                parsed = urlparse(stripped)
                qs = parse_qs(parsed.query)
                if "list" in qs:
                    extra["playlist_id"] = qs["list"][0]
            return ParsedLink(
                url=stripped,
                platform=Platform.YOUTUBE,
                link_type=link_type,
                video_id=vid,
                playlist_id=extra.get("playlist_id", ""),
                extra=extra,
            )

    # 兜底匹配其他已知平台
    platform = _guess_platform(stripped)
    return ParsedLink(
        url=stripped,
        platform=platform,
        link_type=LinkType.SINGLE,
    )

def _guess_platform(url: str) -> Platform:
    host = urlparse(url).hostname or ""
    mapping = {
        "douyin.com": Platform.DOUYIN,
        "iesdouyin.com": Platform.DOUYIN,
        "xiaohongshu.com": Platform.XIAOHONGSHU,
        "xhslink.com": Platform.XIAOHONGSHU,
        "kuaishou.com": Platform.KUAISHOU,
        "tiktok.com": Platform.TIKTOK,
        "twitter.com": Platform.TWITTER,
        "x.com": Platform.TWITTER,
        "instagram.com": Platform.INSTAGRAM,
        "twitch.tv": Platform.TWITCH,
        "vimeo.com": Platform.VIMEO,
        "facebook.com": Platform.FACEBOOK,
        "reddit.com": Platform.REDDIT,
    }
    for domain, plat in mapping.items():
        if domain in host:
            return plat
    return Platform.UNKNOWN
