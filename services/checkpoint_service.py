# -*- coding: utf-8 -*-
"""
Checkpoint Service — 文件系统持久化服务

每一步（转录、分析、渲染）完成后将中间产物序列化为 JSON 写入文件系统，
用于防崩溃恢复和跨接口数据传递（如 /analyze 产物供 /render 读取）。

存储结构:
    reports/{meeting_id}/
        checkpoint_transcribe.json
        checkpoint_analyze.json
        checkpoint_render.json
        final_result.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger


class CheckpointService:
    """
    文件系统持久化服务。

    设计说明:
    - 所有 JSON 文件使用 UTF-8 编码 + ensure_ascii=False（遵守 AGENTS.md 编码死命令）
    - save/load 为异步方法以保持与上层调用链一致，实际 I/O 为同步文件操作
    - 单个 meeting 的所有产物集中在 reports/{meeting_id}/ 目录下
    """

    def __init__(self, base_dir: Path | None = None):
        if base_dir is None:
            from services import _find_project_root
            base_dir = _find_project_root() / "reports"
        self._base_dir = base_dir

    def _meeting_dir(self, meeting_id: str) -> Path:
        """获取指定会议的产物目录，自动创建"""
        d = self._base_dir / meeting_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def save(self, meeting_id: str, stage: str, data: dict[str, Any]) -> Path:
        """
        将中间产物序列化为 JSON 并写入文件。

        Args:
            meeting_id: 会议唯一标识符
            stage: 阶段名称（如 transcribe, analyze, render）
            data: 待持久化的字典数据

        Returns:
            写入的文件路径
        """
        path = self._meeting_dir(meeting_id) / f"checkpoint_{stage}.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"[Checkpoint] 已保存 {stage} 阶段产物: {path}")
        return path

    async def load(self, meeting_id: str, stage: str) -> dict[str, Any] | None:
        """
        从文件读取指定阶段的中间产物。

        Args:
            meeting_id: 会议唯一标识符
            stage: 阶段名称

        Returns:
            反序列化后的字典，文件不存在则返回 None
        """
        path = self._meeting_dir(meeting_id) / f"checkpoint_{stage}.json"
        if not path.exists():
            logger.debug(f"[Checkpoint] 未找到 {stage} 阶段产物: {path}")
            return None
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            logger.info(f"[Checkpoint] 已加载 {stage} 阶段产物: {path}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"[Checkpoint] 读取 {stage} 阶段产物失败: {e}")
            return None

    async def save_final(self, meeting_id: str, data: dict[str, Any]) -> Path:
        """
        保存最终完整结果。

        Args:
            meeting_id: 会议唯一标识符
            data: 完整的最终结果字典

        Returns:
            写入的文件路径
        """
        path = self._meeting_dir(meeting_id) / "final_result.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"[Checkpoint] 已保存最终结果: {path}")
        return path
