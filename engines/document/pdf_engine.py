# -*- coding: utf-8 -*-
"""
PDF 引擎 (LaTeX 编译器)
纯净的 LaTeX 到 PDF 编译引擎，集成了 Tectonic。
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
        将 .tex 文件编译为 .pdf 文件。
        优先使用轻量级的 tectonic，若失败则降级使用较重的 xelatex。
        """
        pdf_path = tex_path.with_suffix(".pdf")
        
        # 1. 尝试使用 Tectonic (从系统 PATH 或项目根目录查找)
        from utils import find_project_root
        local_tectonic = find_project_root() / "tectonic.exe"
        tectonic = str(local_tectonic) if local_tectonic.exists() else shutil.which("tectonic")
        
        if tectonic:
            logger.info("正在使用 Tectonic 进行 LaTeX 编译。")
            cmd = [
                tectonic,
                "-X", "compile",
                "--outdir", str(work_dir),
                str(tex_path)
            ]
            try:
                # 第一次运行 Tectonic 时需要从远端拉取大量宏包(tcolorbox, ctex, fandol字体等)
                # 这个过程可能会超过 2 分钟，因此我们将超时时间调宽到 600 秒
                result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=600, cwd=str(work_dir))
                if result.returncode == 0 and pdf_path.exists():
                    return pdf_path
                logger.warning(f"Tectonic 编译失败: {result.stderr}")
            except Exception as e:
                logger.warning(f"Tectonic 发生异常: {e}")

        # 2. 降级尝试使用 XeLaTeX
        xelatex = shutil.which("xelatex")
        if xelatex:
            logger.info("正在使用 XeLaTeX 进行 LaTeX 编译 (降级模式)。")
            cmd = [
                xelatex,
                "-interaction=nonstopmode",
                "-output-directory", str(work_dir),
                str(tex_path),
            ]
            try:
                # 编译两次以解决交叉引用和目录 (TOC) 问题
                for _ in range(2):
                    subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120, cwd=str(work_dir))
                
                # 检查是否成功生成
                if not pdf_path.exists():
                    # 检查是否输出到了同目录或大小写不同的文件
                    pdf_path = work_dir / tex_path.with_suffix(".pdf").name
                
                if pdf_path.exists():
                    return pdf_path
            except Exception as e:
                logger.error(f"XeLaTeX 发生异常: {e}")

        logger.error("未找到有效的 LaTeX 编译器 (Tectonic/XeLaTeX)，或编译彻底失败。")
        return None
