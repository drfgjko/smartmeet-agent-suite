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

from services import _find_project_root
from services.media_engine import ExtractedFrame
from services.document_engine.pdf_engine import LaTeXNoteBuilder, HTMLNoteBuilder


class ReportRenderer:
    def __init__(self, reports_dir: Path | None = None):
        if reports_dir is None:
            self.reports_dir = _find_project_root() / "reports"
        else:
            self.reports_dir = Path(reports_dir)

    async def render_report(
        self,
        meeting_id: str,
        final_report_md: str,
        kf_objects: list[ExtractedFrame],
        title: str | None = None
    ) -> tuple[Path, Path, Path | None, bool]:
        """
        进行 Markdown 写入以及 LaTeX PDF 生成。
        返回 (md_path, pdf_path, html_path, pdf_generated)
        """
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        import re
        safe_title = ""
        if title:
            safe_title = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', title).strip().strip("_")
            safe_title = safe_title[:50].strip()

        filename_base = f"{meeting_id}_{safe_title}" if safe_title else meeting_id
        md_path = self.reports_dir / f"{filename_base}.md"
        md_path.write_text(final_report_md, encoding="utf-8")
        logger.info(f"[ReportRenderer] Markdown report saved at {md_path}")

        pdf_path = self.reports_dir / f"{filename_base}.pdf"
        html_path = None

        logger.info("[ReportRenderer] Attempting LaTeX XeLaTeX compilation to PDF...")
        latex_builder = LaTeXNoteBuilder()
        assets_tex = _find_project_root() / "assets" / "notes-template.tex"
        template_path = assets_tex if assets_tex.exists() else None

        try:
            tex_content = latex_builder.build_tex(
                notes_md=final_report_md,
                frames=kf_objects,
                title=f"SmartMeet 会议报告",
                meta={"Meeting ID": meeting_id},
                template_path=template_path
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_dir_path = Path(tmpdir)
                tex_file = tmp_dir_path / f"{filename_base}.tex"
                tex_file.write_text(tex_content, encoding="utf-8")

                compiled_pdf = await asyncio.to_thread(latex_builder.compile_pdf, tex_file, tmp_dir_path)
                if compiled_pdf and compiled_pdf.exists():
                    shutil.copy(compiled_pdf, pdf_path)
        except Exception as tex_err:
            logger.warning(f"[ReportRenderer] LaTeX compilation process encountered error: {tex_err}")

        pdf_generated = pdf_path.exists() and pdf_path.stat().st_size > 5000
        if pdf_generated:
            logger.info(f"[ReportRenderer] LaTeX PDF generation succeeded at {pdf_path}")
        else:
            logger.warning("[ReportRenderer] LaTeX PDF generation failed or not installed. Falling back to HTML-to-PDF...")
            try:
                html_builder = HTMLNoteBuilder()
                html_content = html_builder.build_html(
                    notes_md=final_report_md,
                    frames=kf_objects,
                    title="SmartMeet 会议报告",
                    meta={"Meeting ID": meeting_id}
                )
                html_path = self.reports_dir / f"{filename_base}.html"
                html_path.write_text(html_content, encoding="utf-8")
                logger.info(f"[ReportRenderer] Fallback HTML report saved at {html_path}")

                success = HTMLNoteBuilder.html_to_pdf(html_path, pdf_path)
                if success:
                    pdf_generated = True
                    logger.info(f"[ReportRenderer] Fallback HTML to PDF generation succeeded at {pdf_path}")
                else:
                    logger.error("[ReportRenderer] Fallback HTML to PDF generation failed: PDF missing or too small")
            except Exception as html_err:
                logger.error(f"[ReportRenderer] Error during HTML-to-PDF fallback: {html_err}")

        return md_path, pdf_path, html_path, pdf_generated
