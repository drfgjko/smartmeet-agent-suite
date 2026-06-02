# -*- coding: utf-8 -*-
"""
Mindmap Service
- 负责调用 MindMapPipeline 生成会议思维导图并保存为 Markdown 文件
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from loguru import logger
from typing import Any

from utils import find_project_root
from services.document_engine.mindmap_engine import MindMapPipeline


class MindMapService:
    def __init__(self, llm_client: Any = None, reports_dir: Path | None = None):
        self.llm = llm_client
        if reports_dir is None:
            self.reports_dir = find_project_root() / "reports"
        else:
            self.reports_dir = Path(reports_dir)

    async def generate_and_save_mindmap(self, meeting_id: str, final_report_md: str, title: str | None = None) -> tuple[Path, bool]:
        """
        生成 Mermaid 思维导图文件。
        返回 (mindmap_path, mindmap_generated)
        """
        target_dir = self.reports_dir / meeting_id
        target_dir.mkdir(parents=True, exist_ok=True)

        import re
        safe_title = ""
        if title:
            safe_title = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', title).strip().strip("_")
            safe_title = safe_title[:50].strip()

        filename_base = f"{meeting_id}_{safe_title}" if safe_title else meeting_id
        mindmap_path = target_dir / f"{filename_base}_mindmap.md"
        mindmap_generated = False

        try:
            logger.info("[MindMapService] 正在生成 Mermaid 思维导图...")
            mindmap_pipeline = MindMapPipeline(llm_client=self.llm)
            await mindmap_pipeline.async_save_mindmap(final_report_md, mindmap_path)
            mindmap_generated = mindmap_path.exists()
            if mindmap_generated:
                logger.info(f"[MindMapService] 思维导图已保存至 {mindmap_path}")
        except Exception as mm_err:
            logger.error(f"[MindMapService] 思维导图生成失败: {mm_err}")

        return mindmap_path, mindmap_generated
