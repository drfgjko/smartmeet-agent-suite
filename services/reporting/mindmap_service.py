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

from services.document_engine.mindmap_engine import MindMapPipeline


class MindMapService:
    def __init__(self, llm_client: Any = None, reports_dir: Path | None = None):
        self.llm = llm_client
        if reports_dir is None:
            self.reports_dir = Path(__file__).resolve().parents[2] / "reports"
        else:
            self.reports_dir = Path(reports_dir)

    async def generate_and_save_mindmap(self, meeting_id: str, final_report_md: str) -> tuple[Path, bool]:
        """
        生成 Mermaid 思维导图文件。
        返回 (mindmap_path, mindmap_generated)
        """
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        mindmap_path = self.reports_dir / f"{meeting_id}_mindmap.md"
        mindmap_generated = False

        try:
            logger.info("[MindMapService] Generating Mermaid mindmap...")
            mindmap_pipeline = MindMapPipeline(llm_client=self.llm)
            await asyncio.to_thread(mindmap_pipeline.save_mindmap, final_report_md, mindmap_path)
            mindmap_generated = mindmap_path.exists()
            if mindmap_generated:
                logger.info(f"[MindMapService] Mindmap saved at {mindmap_path}")
        except Exception as mm_err:
            logger.error(f"[MindMapService] Mindmap generation failed: {mm_err}")

        return mindmap_path, mindmap_generated
