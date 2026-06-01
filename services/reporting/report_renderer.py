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
from services.document_engine.pdf_engine import LaTeXNoteBuilder
from services.document_engine.html_engine import HTMLNoteBuilder


class ReportRenderer:
    def __init__(self, reports_dir: Path | None = None, llm_client: Any = None):
        if reports_dir is None:
            self.reports_dir = _find_project_root() / "reports"
        else:
            self.reports_dir = Path(reports_dir)
        self.llm_client = llm_client

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
        
        # 清理可能存在的旧文件，防止报错时产生成功生成的误判
        if pdf_path.exists():
            pdf_path.unlink()

        logger.info("[ReportRenderer] Attempting direct LaTeX generation via LLM...")
        tex_content = ""
        pdf_generated = False
        
        if self.llm_client:
            try:
                from services.document_engine.templates.latex_base import build_latex_prompt
                prompt = build_latex_prompt(
                    title=title or "SmartMeet 会议报告",
                    duration_sec=0.0,
                    uploader="SmartMeet",
                    transcript=final_report_md,
                )
                
                messages = [
                    {"role": "system", "content": "You are an expert LaTeX typesetter. Output only valid LaTeX code without any markdown formatting or explanations."},
                    {"role": "user", "content": prompt}
                ]
                
                tex_content = await self.llm_client.chat(messages=messages, temperature=0.2, max_tokens=6000)
                tex_content = re.sub(r"```[a-zA-Z]*\n(.*?)\n```", r"\1", tex_content, flags=re.DOTALL).strip()
            except Exception as llm_err:
                logger.error(f"[ReportRenderer] LLM LaTeX generation failed: {llm_err}")

        if tex_content:
            try:
                latex_builder = LaTeXNoteBuilder()
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_dir_path = Path(tmpdir)
                    tex_file = tmp_dir_path / f"{filename_base}.tex"
                    tex_file.write_text(tex_content, encoding="utf-8")

                    # 把关键帧图片拷贝到编译临时目录，统一命名为 image_1, image_2...
                    if kf_objects:
                        for idx, kf in enumerate(kf_objects, 1):
                            if kf.path and Path(kf.path).exists():
                                ext = Path(kf.path).suffix
                                dest = tmp_dir_path / f"image_{idx}{ext}"
                                shutil.copy(kf.path, dest)

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
                from services.document_engine.html_engine import HTMLNoteBuilder
                html_builder = HTMLNoteBuilder()
                html_content = html_builder.build_html(
                    notes_md=final_report_md,
                    frames=kf_objects,
                    title=title or "SmartMeet 会议报告",
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
