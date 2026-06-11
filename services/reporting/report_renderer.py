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

from utils import find_project_root
from engines.media import ExtractedFrame
from engines.document.pdf_engine import LaTeXNoteBuilder
from engines.document.html_engine import HTMLNoteBuilder


class ReportRenderer:
    def __init__(self, reports_dir: Path | None = None, llm_client: Any = None):
        if reports_dir is None:
            from utils import get_reports_dir
            self.reports_dir = get_reports_dir()
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
        target_dir = self.reports_dir / meeting_id
        target_dir.mkdir(parents=True, exist_ok=True)

        import re
        safe_title = ""
        if title:
            safe_title = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', title).strip().strip("_")
            safe_title = safe_title[:50].strip()

        filename_base = f"{meeting_id}_{safe_title}" if safe_title else meeting_id
        md_path = target_dir / f"{filename_base}.md"
        md_path.write_text(final_report_md, encoding="utf-8")
        logger.info(f"[ReportRenderer] Markdown 报告已保存至 {md_path}")

        pdf_path = target_dir / f"{filename_base}.pdf"
        html_path = None
        
        # 清理可能存在的旧文件，防止报错时产生成功生成的误判
        if pdf_path.exists():
            pdf_path.unlink()

        logger.info("[ReportRenderer] 正在尝试通过大模型直接生成 LaTeX...")
        tex_content = ""
        pdf_generated = False
        
        try:
            logger.info("[ReportRenderer] 正在通过纯 Python 解析器生成 LaTeX...")
            import time
            from engines.document.templates.latex_base import LATEX_PREAMBLE, LATEX_POSTAMBLE
            from engines.document.markdown_parser import MarkdownToLatexConverter
            
            date_str = time.strftime("%Y-%m-%d")
            preamble = LATEX_PREAMBLE.replace("{title}", title or "SmartMeet 会议报告")
            preamble = preamble.replace("{uploader}", "SmartMeet")
            preamble = preamble.replace("{date_str}", date_str)
            
            parser = MarkdownToLatexConverter()
            body_tex = parser.convert(final_report_md)
            
            tex_content = preamble + "\n" + body_tex + "\n" + LATEX_POSTAMBLE
        except Exception as parse_err:
            logger.error(f"[ReportRenderer] Python LaTeX 解析失败: {parse_err}")

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
                logger.warning(f"[ReportRenderer] LaTeX 编译过程遇到错误: {tex_err}")

        pdf_generated = pdf_path.exists() and pdf_path.stat().st_size > 5000
        if pdf_generated:
            logger.info(f"[ReportRenderer] LaTeX PDF 讲义生成成功，保存至 {pdf_path}")
        else:
            logger.warning("[ReportRenderer] LaTeX PDF 生成失败或未安装引擎。回退到 HTML-to-PDF 降级模式...")
            try:
                from engines.document.html_engine import HTMLNoteBuilder
                html_builder = HTMLNoteBuilder()
                html_content = html_builder.build_html(
                    notes_md=final_report_md,
                    frames=kf_objects,
                    title=title or "SmartMeet 会议报告",
                    meta={"Meeting ID": meeting_id}
                )
                html_path = target_dir / f"{filename_base}.html"
                html_path.write_text(html_content, encoding="utf-8")
                logger.info(f"[ReportRenderer] 降级模式 HTML 报告已保存至 {html_path}")

                success = HTMLNoteBuilder.html_to_pdf(html_path, pdf_path)
                if success:
                    pdf_generated = True
                    logger.info(f"[ReportRenderer] 降级模式 HTML 转 PDF 成功，保存至 {pdf_path}")
                else:
                    logger.error("[ReportRenderer] 降级模式 HTML 转 PDF 失败: 文件丢失或体积过小")
            except Exception as html_err:
                logger.error(f"[ReportRenderer] HTML-to-PDF 降级模式执行时出错: {html_err}")

        return md_path, pdf_path, html_path, pdf_generated
