# -*- coding: utf-8 -*-
"""
HTML Note Builder for generating HTML fallback reports.
"""

from __future__ import annotations

import re
import os
import shutil
import platform
import subprocess
from pathlib import Path
from loguru import logger

from utils import find_project_root
from services.media_engine import ExtractedFrame

class HTMLNoteBuilder:
    def __init__(self):
        css_path = find_project_root() / "assets" / "style.css"
        if not css_path.exists():
            # Fallback inline CSS if file not found
            css = "body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }"
        else:
            css = css_path.read_text(encoding="utf-8")
        self.style_tag = f"<style>\n{css}\n</style>"

    def build_html(
        self,
        notes_md: str,
        frames: list[ExtractedFrame],
        title: str,
        meta: dict[str, str] | None = None,
        cover_path: Path | None = None,
    ) -> str:
        if meta is None:
            meta = {}

        def _replace_img(match):
            n = int(match.group(1))
            if 1 <= n <= len(frames):
                fr = frames[n - 1]
                abs_path = str(fr.path.resolve())
                cap = fr.caption or fr.subtitle_text or f"video {fr.timestamp_str}"
                return (
                    f'\n<img src="file://{abs_path}" alt="frame {n}">\n'
                    f'<div class="frame-caption">Fig.{n} — {cap} ({fr.timestamp_str})</div>\n'
                )
            return f"*(Fig.{n})*"

        body = re.sub(r"\{IMAGE:(\d+)\}", _replace_img, notes_md)

        body = re.sub(
            r"\{IMPORTANT\}(.*?)\{/IMPORTANT\}",
            r'<div class="important-box">\1</div>',
            body, flags=re.DOTALL,
        )
        body = re.sub(
            r"\{KNOWLEDGE\}(.*?)\{/KNOWLEDGE\}",
            r'<div class="knowledge-box">\1</div>',
            body, flags=re.DOTALL,
        )
        body = re.sub(
            r"\{WARNING\}(.*?)\{/WARNING\}",
            r'<div class="warning-box">\1</div>',
            body, flags=re.DOTALL,
        )

        import markdown
        body = "[TOC]\n\n" + body
        body = markdown.markdown(body, extensions=['fenced_code', 'tables', 'toc'])

        cover_html = ""
        if cover_path and cover_path.exists():
            cover_html = f'<img src="file://{cover_path.resolve()}" alt="cover">'
        meta_rows = "\n".join(
            f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
            for k, v in meta.items()
        )

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
{self.style_tag}
</head>
<body>
<div class="cover">
<h1>{title}</h1>
{cover_html}
<table style="max-width:500px;margin:2rem auto">{meta_rows}</table>
</div>
{body}
</body>
</html>"""
        return html

    @staticmethod
    def html_to_pdf(html_path: Path, pdf_path: Path) -> bool:
        try:
            from weasyprint import HTML
            logger.info(f"Using WeasyPrint to render native PDF to {pdf_path}")
            HTML(filename=str(html_path.resolve())).write_pdf(str(pdf_path.resolve()))
            return pdf_path.exists() and pdf_path.stat().st_size > 5000
        except Exception as e:
            logger.warning(f"WeasyPrint failed ({e}). Falling back to zero-dependency Chrome Headless...")
            
            chrome = None
            if platform.system() == "Windows":
                paths = [
                    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
                    Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
                    Path(os.environ.get("LocalAppData", "C:\\Users\\Default\\AppData\\Local")) / "Google" / "Chrome" / "Application" / "chrome.exe",
                    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                ]
                for p in paths:
                    if p.exists():
                        chrome = str(p)
                        break

            if not chrome:
                chrome = (
                    shutil.which("chrome") or shutil.which("chrome.exe") or 
                    shutil.which("msedge") or shutil.which("msedge.exe") or 
                    shutil.which("google-chrome") or shutil.which("chromium")
                )

            if not chrome:
                logger.error("No WeasyPrint, and no Chrome/Edge found. PDF generation failed.")
                return False

            cmd = [
                chrome, "--headless=new",
                f"--print-to-pdf={pdf_path}",
                "--print-to-pdf-no-header", "--no-sandbox", "--disable-gpu",
                f"file://{html_path.resolve()}",
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=60)
            except Exception as ce:
                logger.error(f"Failed to run chrome headlessly: {ce}")
                return False

            return pdf_path.exists() and pdf_path.stat().st_size > 5000
