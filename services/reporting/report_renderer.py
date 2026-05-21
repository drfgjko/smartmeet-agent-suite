# -*- coding: utf-8 -*-
"""
Report Renderer Service
- 负责 Markdown 持久化
- LaTeX / HTML 双轨 PDF 编译及降级生成
"""

from __future__ import annotations

import shutil
import asyncio
import tempfile
from pathlib import Path
from loguru import logger
from typing import Any

from services.media_engine import ExtractedFrame
from services.document_engine.pdf_engine import LaTeXNoteBuilder, HTMLNoteBuilder


class ReportRenderer:
    def __init__(self, reports_dir: Path | None = None):
        if reports_dir is None:
            # services/reporting/report_renderer.py -> parents[2] is smartmeet-agent-suite/
            self.reports_dir = Path(__file__).resolve().parents[2] / "reports"
        else:
            self.reports_dir = Path(reports_dir)

    async def render_report(
        self,
        meeting_id: str,
        final_report_md: str,
        kf_objects: list[ExtractedFrame]
    ) -> tuple[Path, Path, Path | None, bool]:
        """
        进行 Markdown 写入以及 PDF 双轨生成。
        返回 (md_path, pdf_path, html_path, pdf_generated)
        """
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        md_path = self.reports_dir / f"{meeting_id}.md"
        # 强制指定 utf-8
        md_path.write_text(final_report_md, encoding="utf-8")
        logger.info(f"[ReportRenderer] Markdown report saved at {md_path}")

        pdf_path = self.reports_dir / f"{meeting_id}.pdf"
        pdf_generated = False
        html_path = None

        # 轨道 1: XeLaTeX 渲染
        try:
            logger.info("[ReportRenderer] Attempting LaTeX XeLaTeX compilation to PDF...")
            latex_builder = LaTeXNoteBuilder()
            assets_tex = Path(__file__).resolve().parents[2] / "assets" / "notes-template.tex"
            template_path = assets_tex if assets_tex.exists() else None

            tex_content = latex_builder.build_tex(
                notes_md=final_report_md,
                frames=kf_objects,
                title=f"SmartMeet 会议报告",
                meta={"Meeting ID": meeting_id},
                template_path=template_path
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_dir_path = Path(tmpdir)
                tex_file = tmp_dir_path / f"{meeting_id}.tex"
                tex_file.write_text(tex_content, encoding="utf-8")

                compiled_pdf = await asyncio.to_thread(latex_builder.compile_pdf, tex_file, tmp_dir_path)
                if compiled_pdf and compiled_pdf.exists():
                    shutil.copy(compiled_pdf, pdf_path)
                    pdf_generated = pdf_path.exists() and pdf_path.stat().st_size > 5000
                    if pdf_generated:
                        logger.info(f"[ReportRenderer] XeLaTeX PDF generation succeeded at {pdf_path}")
        except Exception as latex_err:
            logger.warning(f"[ReportRenderer] LaTeX compilation failed: {latex_err}. Falling back to HTML rendering.")

        # 轨道 2: HTML 浏览器无头打印降级
        if not pdf_generated:
            try:
                logger.info("[ReportRenderer] Falling back to HTML Note Builder for PDF rendering...")
                html_builder = HTMLNoteBuilder()
                html_content = html_builder.build_html(
                    notes_md=final_report_md,
                    frames=kf_objects,
                    title=f"SmartMeet 会议报告",
                    meta={"Meeting ID": meeting_id}
                )
                html_path = self.reports_dir / f"{meeting_id}.html"
                html_path.write_text(html_content, encoding="utf-8")
                logger.info(f"[ReportRenderer] HTML report saved at {html_path}")

                success = await asyncio.to_thread(html_builder.html_to_pdf, html_path, pdf_path)
                pdf_generated = success and pdf_path.exists() and pdf_path.stat().st_size > 5000
                if pdf_generated:
                    logger.info(f"[ReportRenderer] HTML-to-PDF generation succeeded at {pdf_path}")
                else:
                    logger.warning("[ReportRenderer] HTML-to-PDF failed or generated empty PDF")
            except Exception as html_err:
                logger.error(f"[ReportRenderer] HTML fallback rendering failed: {html_err}")

        return md_path, pdf_path, html_path, pdf_generated
