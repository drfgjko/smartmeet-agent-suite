# -*- coding: utf-8 -*-
"""
PDF Engine (LaTeX Compiler)
Pure engine for compiling direct LaTeX code to PDF, with Tectonic integration.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from loguru import logger

class LaTeXNoteBuilder:
    def compile_pdf(self, tex_path: Path, work_dir: Path) -> Path | None:
        """
        Compiles a .tex file to .pdf.
        It prioritizes tectonic (lightweight) over xelatex (heavy).
        """
        pdf_path = tex_path.with_suffix(".pdf")
        
        # 1. Try Tectonic (system PATH or project root)
        from services import _find_project_root
        local_tectonic = _find_project_root() / "tectonic.exe"
        tectonic = str(local_tectonic) if local_tectonic.exists() else shutil.which("tectonic")
        
        if tectonic:
            logger.info("Using Tectonic for LaTeX compilation.")
            cmd = [
                tectonic,
                "-X", "compile",
                "--outdir", str(work_dir),
                str(tex_path)
            ]
            try:
                # 第一次运行 Tectonic 时需要从远端拉取大量宏包(tcolorbox, ctex, fandol字体等)
                # 这个过程可能会超过 2 分钟，因此我们将超时时间调宽到 600 秒
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(work_dir))
                if result.returncode == 0 and pdf_path.exists():
                    return pdf_path
                logger.warning(f"Tectonic compilation failed: {result.stderr}")
            except Exception as e:
                logger.warning(f"Tectonic encountered an error: {e}")

        # 2. Try XeLaTeX as fallback
        xelatex = shutil.which("xelatex")
        if xelatex:
            logger.info("Using XeLaTeX for LaTeX compilation (fallback).")
            cmd = [
                xelatex,
                "-interaction=nonstopmode",
                "-output-directory", str(work_dir),
                str(tex_path),
            ]
            try:
                # Two passes to resolve cross-references/TOC
                for _ in range(2):
                    subprocess.run(cmd, capture_output=True, timeout=120, cwd=str(work_dir))
                
                # Check if generated
                if not pdf_path.exists():
                    # check if it output with different casing or same directory
                    pdf_path = work_dir / tex_path.with_suffix(".pdf").name
                
                if pdf_path.exists():
                    return pdf_path
            except Exception as e:
                logger.error(f"XeLaTeX encountered an error: {e}")

        logger.error("No valid LaTeX compiler (Tectonic/XeLaTeX) found, or compilation failed.")
        return None
