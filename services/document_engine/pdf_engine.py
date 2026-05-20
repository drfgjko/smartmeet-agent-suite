# -*- coding: utf-8 -*-
"""
Illustrated Lecture Note Generator（图文版式生成引擎）
- 多模态输出缝合：融合视频关键帧、文本纪要、发言人排版
- 支持多级富文本模版渲染：重点难点标注、注意标志、代码块与 LaTeX 公式支持
- 提供 LaTeX (XeLaTeX) 级专业排版生成与 HTML + Headless Chrome 双轨渲染机制
- 适配 Windows 平台自动搜索 Chrome/Edge 浏览器路径，保证本地 PDF 转换可用性
- 多线程并发加速多视频合集纪要排版生成
- 模版读取：直接读取项目根目录 assets 中的 style.css 和 notes-template.tex，不存在则 Fail-Fast
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from loguru import logger

from services.media_engine import ExtractedFrame, extract_keyframes, align_frames_to_subtitles, download_video

@dataclass
class EpisodeResult:
    episode: int
    title: str
    duration: float
    frames: list[ExtractedFrame]
    subtitle_text: str
    notes_md: str = ""
    notes_tex: str = ""
    pdf_path: Path | None = None
    html_path: Path | None = None

@dataclass
class CollectionResult:
    title: str
    episodes: list[EpisodeResult]
    merged_pdf: Path | None = None
    merged_html: Path | None = None

class HTMLNoteBuilder:
    def __init__(self):
        css_path = Path(__file__).resolve().parents[2] / "assets" / "style.css"
        if not css_path.exists():
            raise FileNotFoundError(f"Required CSS template not found at {css_path}")
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
                shutil.which("chrome")
                or shutil.which("chrome.exe")
                or shutil.which("msedge")
                or shutil.which("msedge.exe")
                or shutil.which("google-chrome")
                or shutil.which("chromium")
            )

        if not chrome:
            logger.warning("No Headless Chrome or Edge found in system path. Skip PDF generation.")
            return False

        cmd = [
            chrome, "--headless=new",
            f"--print-to-pdf={pdf_path}",
            "--print-to-pdf-no-header", "--no-sandbox", "--disable-gpu",
            f"file://{html_path.resolve()}",
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=60)
        except Exception as e:
            logger.error(f"Failed to run chrome headlessly: {e}")
            return False

        return pdf_path.exists() and pdf_path.stat().st_size > 5000

class LaTeXNoteBuilder:
    def build_tex(
        self,
        notes_md: str,
        frames: list[ExtractedFrame],
        title: str,
        meta: dict[str, str] | None = None,
        cover_path: Path | None = None,
        template_path: Path | None = None,
    ) -> str:
        if meta is None:
            meta = {}

        if template_path and template_path.exists():
            tex = template_path.read_text(encoding="utf-8")
        else:
            tex = self._default_template()

        tex = tex.replace("[TITLE]", _tex_escape(title))
        tex = tex.replace("[DATE]", time.strftime("%Y-%m-%d"))
        tex = tex.replace("[CHANNEL]", _tex_escape(meta.get("uploader", "")))
        tex = tex.replace("[DURATION]", meta.get("duration", ""))
        tex = tex.replace("[URL]", meta.get("url", ""))

        if cover_path and cover_path.exists():
            tex = tex.replace("[COVER_PATH]", str(cover_path.resolve()))
        else:
            tex = tex.replace("[COVER_PATH]", "")

        body = self._md_to_tex(notes_md, frames)
        tex = tex.replace("[BODY]", body)
        return tex

    def compile_pdf(self, tex_path: Path, work_dir: Path) -> Path | None:
        xelatex = shutil.which("xelatex")
        if not xelatex:
            return None
        cmd = [
            xelatex,
            "-interaction=nonstopmode",
            "-output-directory", str(work_dir),
            str(tex_path),
        ]
        for _ in range(2):
            subprocess.run(cmd, capture_output=True, timeout=120, cwd=str(work_dir))
        pdf = tex_path.with_suffix(".pdf")
        if not pdf.exists():
            pdf = work_dir / tex_path.with_suffix(".pdf").name
        return pdf if pdf.exists() else None

    def _md_to_tex(self, md: str, frames: list[ExtractedFrame]) -> str:
        BOX_TAGS = {"IMPORTANT": "importantbox", "KNOWLEDGE": "knowledgebox",
                    "WARNING": "warningbox", "DECISION": "decisionbox", "ACTION": "actionbox"}
        for tag in BOX_TAGS:
            md = re.sub(
                rf"\{{{tag}\}}(.*?)\{{/{tag}\}}",
                rf"{{{tag}}}\n\1\n{{/{tag}}}",
                md, flags=re.DOTALL,
            )

        lines = md.split("\n")
        tex_lines = []
        in_code = False
        in_table = False
        is_header = False
        code_lang = ""
        open_boxes: list[str] = []

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("```"):
                if in_code:
                    tex_lines.append("\\end{lstlisting}")
                    in_code = False
                else:
                    code_lang = stripped.replace("```", "").strip() or "python"
                    tex_lines.append(f"\\begin{{lstlisting}}[language={code_lang}]")
                    in_code = True
                continue

            if in_code:
                tex_lines.append(line)
                continue

            img_match = re.match(r"\s*\{IMAGE:(\d+)\}", stripped)
            if img_match:
                n = int(img_match.group(1))
                if 1 <= n <= len(frames):
                    fr = frames[n - 1]
                    cap = fr.caption or fr.subtitle_text or f"video {fr.timestamp_str}"
                    tex_lines.append("\\begin{figure}[H]")
                    tex_lines.append("\\centering")
                    tex_lines.append(
                        f"\\includegraphics[width=0.9\\textwidth]{{{fr.path.resolve()}}}"
                    )
                    tex_lines.append(
                        f"\\caption{{{_tex_escape(cap)} \\protect\\footnotemark}}"
                    )
                    tex_lines.append("\\end{figure}")
                    tex_lines.append(
                        f"\\footnotetext{{video time: {fr.timestamp_str}}}"
                    )
                continue

            box_handled = False
            for tag, env in BOX_TAGS.items():
                LABELS = {"importantbox": "重点", "knowledgebox": "知识补充",
                          "warningbox": "注意", "decisionbox": "决策", "actionbox": "行动项"}
                if stripped == f"{{{tag}}}":
                    tex_lines.append(f"\\begin{{ {env} }}{{{LABELS.get(env, tag)}}}")
                    open_boxes.append(env)
                    box_handled = True
                    break
                if stripped == f"{{/{tag}}}":
                    tex_lines.append(f"\\end{{{env}}}")
                    if open_boxes and open_boxes[-1] == env:
                        open_boxes.pop()
                    box_handled = True
                    break
            if box_handled:
                continue

            if stripped.startswith("# ") and not stripped.startswith("## "):
                tex_lines.append(f"\\section*{{{_tex_escape(stripped[2:].strip())}}}")
                continue
            if line.startswith("## "):
                tex_lines.append(f"\\section{{{_tex_escape(line[3:].strip())}}}")
                continue
            if line.startswith("### "):
                tex_lines.append(f"\\subsection{{{_tex_escape(line[4:].strip())}}}")
                continue
            if line.startswith("#### "):
                tex_lines.append(f"\\subsubsection{{{_tex_escape(line[5:].strip())}}}")
                continue

            if stripped in ("---", "***", "___"):
                tex_lines.append("\\bigskip\\hrule\\bigskip")
                continue

            if stripped.startswith("> "):
                tex_lines.append(f"\\begin{{quote}}\\textit{{{_tex_escape(stripped[2:])}}}\\end{{quote}}")
                continue

            if "|" in stripped and stripped.startswith("|"):
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                if all(set(c) <= set("-: ") for c in cells):
                    continue
                if not in_table:
                    ncols = len(cells)
                    col_spec = "|" + "l|" * ncols
                    tex_lines.append("\\begin{center}")
                    tex_lines.append(f"\\begin{{tabular}}{{{col_spec}}}")
                    tex_lines.append("\\hline")
                    in_table = True
                    is_header = True
                row = " & ".join(_tex_escape(c) for c in cells)
                tex_lines.append(f"{row} \\\\")
                tex_lines.append("\\hline")
                if is_header:
                    is_header = False
                continue
            elif in_table:
                tex_lines.append("\\end{tabular}")
                tex_lines.append("\\end{center}")
                in_table = False

            processed = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", line)
            processed = re.sub(r"\*(.+?)\*", r"\\textit{\1}", processed)
            processed = re.sub(r"`([^`]+)`", r"\\texttt{\1}", processed)
            processed = re.sub(r"\$(.+?)\$", r"$\1$", processed)

            tex_lines.append(processed)

        if in_table:
            tex_lines.append("\\end{tabular}")
            tex_lines.append("\\end{center}")

        for env in reversed(open_boxes):
            tex_lines.append(f"\\end{{{env}}}")

        return "\n".join(tex_lines)

    @staticmethod
    def _default_template() -> str:
        tex_path = Path(__file__).resolve().parents[2] / "assets" / "notes-template.tex"
        if not tex_path.exists():
            raise FileNotFoundError(f"Required LaTeX template not found at {tex_path}")
        return tex_path.read_text(encoding="utf-8")

class PDFPipeline:
    def __init__(
        self,
        llm_client: Any = None,
        max_tokens: int = 4000,
        concurrency: int = 3,
    ):
        from services.integrations.llm_client import create_llm_client
        self.llm = llm_client or create_llm_client()
        self.max_tokens = max_tokens
        self.concurrency = concurrency
        self.html_builder = HTMLNoteBuilder()
        self.latex_builder = LaTeXNoteBuilder()

    def process_episode(
        self,
        video_url: str,
        episode_num: int,
        title: str,
        work_dir: Path,
        output_dir: Path,
        total_episodes: int = 1,
        subtitle_text: str = "",
        max_frames: int = 15,
    ) -> EpisodeResult:
        ep_work = work_dir / f"ep{episode_num:02d}"
        ep_work.mkdir(parents=True, exist_ok=True)
        frames_dir = ep_work / "frames"

        video_path = ep_work / "video.mp4"
        if not (video_path.exists() and video_path.stat().st_size > 50000):
            try:
                downloaded_file = download_video(video_url, ep_work)
                shutil.move(downloaded_file, video_path)
            except Exception as e:
                logger.error(f"Download video failed: {e}. Attempting direct subprocess...")
                self._download_video_fallback(video_url, video_path)

        duration = 0.0
        if video_path.exists():
            from services.media_engine import get_duration
            duration = get_duration(video_path)

        if video_path.exists():
            frames = extract_keyframes(video_path, frames_dir, max_frames=max_frames)
            if subtitle_text:
                from services.media_engine import parse_srt
                if isinstance(subtitle_text, str) and subtitle_text.endswith(".srt") and Path(subtitle_text).exists():
                    segs = parse_srt(Path(subtitle_text))
                    frames = align_frames_to_subtitles(frames, segs)
                elif isinstance(subtitle_text, str) and subtitle_text:
                    pass
        else:
            frames = []

        notes_md = self._generate_notes(
            episode_num, title, duration, subtitle_text, frames, total_episodes
        )

        meta = {
            "Episode": f"{episode_num}/{total_episodes}",
            "Title": title,
            "Duration": f"{int(duration//60)}m{int(duration%60)}s",
        }

        html_content = self.html_builder.build_html(notes_md, frames, title, meta)
        html_path = output_dir / f"ep{episode_num:02d}_{_safe(title)}.html"
        html_path.write_text(html_content, encoding="utf-8")

        pdf_path = html_path.with_suffix(".pdf")
        HTMLNoteBuilder.html_to_pdf(html_path, pdf_path)

        result = EpisodeResult(
            episode=episode_num,
            title=title,
            duration=duration,
            frames=frames,
            subtitle_text=subtitle_text,
            notes_md=notes_md,
            html_path=html_path,
            pdf_path=pdf_path if pdf_path.exists() else None,
        )
        return result

    def process_collection(
        self,
        episodes: list[dict],
        work_dir: Path,
        output_dir: Path,
        collection_title: str = "Video Collection",
    ) -> CollectionResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(episodes)
        results: list[EpisodeResult] = [None] * total  # type: ignore

        def _do_one(idx: int) -> EpisodeResult:
            ep = episodes[idx]
            r = self.process_episode(
                video_url=ep["url"],
                episode_num=idx + 1,
                title=ep["title"],
                work_dir=work_dir,
                output_dir=output_dir / "episodes",
                total_episodes=total,
                subtitle_text=ep.get("subtitle_text", ""),
            )
            return r

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = {pool.submit(_do_one, i): i for i in range(total)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error(f"Episode {idx+1} processing failed: {e}")
                    results[idx] = EpisodeResult(
                        episode=idx + 1,
                        title=episodes[idx]["title"],
                        duration=0,
                        frames=[],
                        subtitle_text="",
                        notes_md=f"*Generation failed: {e}*",
                    )

        merged_html = self._merge_html(results, collection_title, output_dir)
        merged_pdf = merged_html.with_suffix(".pdf")
        HTMLNoteBuilder.html_to_pdf(merged_html, merged_pdf)

        return CollectionResult(
            title=collection_title,
            episodes=results,
            merged_pdf=merged_pdf if merged_pdf.exists() else None,
            merged_html=merged_html,
        )

    def _download_video_fallback(self, url: str, output: Path) -> None:
        cmd = (
            f'yt-dlp "{url}" '
            f'-f "bestvideo[height<=720]+bestaudio/best[height<=720]" '
            f'--merge-output-format mp4 '
            f'-o "{output}" --no-warnings --quiet'
        )
        subprocess.run(cmd, shell=True, capture_output=True, timeout=300)

    def _generate_notes(
        self,
        ep_num: int,
        title: str,
        duration: float,
        subtitle_text: str,
        frames: list[ExtractedFrame],
        total: int,
    ) -> str:
        frames_desc = ""
        if frames:
            frames_desc = "Available keyframes:\n" + "\n".join(
                f"  Fig.{i+1} at {f.timestamp_str}: {f.subtitle_text[:60] or '(no subtitle)'}"
                for i, f in enumerate(frames)
            )

        mins = int(duration // 60)
        secs = int(duration % 60)

        prompt = f"""Generate detailed illustrated lecture notes for this video episode.

Episode: {ep_num}/{total} "{title}" ({mins}m{secs}s)

Transcript:
{subtitle_text[:6000] if subtitle_text else "(No transcript; generate notes based on the title and topic)"}

{frames_desc}

FORMAT REQUIREMENTS:
1. Use ## for sections, ### for subsections
2. Insert {{IMAGE:N}} where figure N should appear (e.g. {{IMAGE:1}}, {{IMAGE:2}})
3. Use highlight boxes for key concepts:
   {{IMPORTANT}}Key concept text{{/IMPORTANT}}
   {{KNOWLEDGE}}Background knowledge{{/KNOWLEDGE}}
   {{WARNING}}Common pitfall{{/WARNING}}
4. Include code blocks with ``` when code appears
5. Use LaTeX math ($...$) for formulas
6. End each section with a brief summary
7. Write in Chinese

CONTENT REQUIREMENTS:
- Detailed, structured, suitable for serious study
- Each figure reference must have a descriptive caption below it
- Include code with detailed comments when relevant
- Cover all major points from the transcript
- Add a final summary section with key takeaways"""

        return self._call_llm(prompt)

    def _call_llm(self, prompt: str, retries: int = 3) -> str:
        system = "You are a professional technical education expert. Output lecture notes directly in Markdown format with the specified markers. Do not wrap output in think tags."

        for attempt in range(retries):
            try:
                full = ""
                stream = self.llm.chat_stream_sync(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=self.max_tokens,
                    timeout=120,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    full += delta
                full = re.sub(r"<think>.*?</think>", "", full, flags=re.DOTALL).strip()
                if len(full) > 200:
                    return full
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep((attempt + 1) * 8)
                else:
                    return f"*Note generation failed after {retries} attempts: {e}*"
        return ""

    def _merge_html(
        self, episodes: list[EpisodeResult], title: str, output_dir: Path
    ) -> Path:
        css_path = Path(__file__).resolve().parents[2] / "assets" / "style.css"
        if not css_path.exists():
            raise FileNotFoundError(f"Required CSS template not found at {css_path}")
        css = css_path.read_text(encoding="utf-8")

        parts = [f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{title}</title>
<style>
{css}
</style>
</head><body>
<div class="cover"><h1>{title}</h1>
<p>Generated by Smartmeet &middot; {time.strftime('%Y-%m-%d')}</p>
</div>
<div class="toc"><h2>Table of Contents</h2><ol>"""]

        for ep in episodes:
            if ep:
                parts.append(f'<li><a href="#ep{ep.episode}">{ep.title}</a></li>')
        parts.append("</ol></div>")

        for ep in episodes:
            if not ep:
                continue
            parts.append(f'<h1 id="ep{ep.episode}">Ep.{ep.episode}: {ep.title}</h1>')

            body = ep.notes_md
            def _rep(m, ep=ep):
                n = int(m.group(1))
                if 1 <= n <= len(ep.frames):
                    fr = ep.frames[n - 1]
                    return (
                        f'\n<img src="file://{fr.path.resolve()}" alt="frame">\n'
                        f'<div class="frame-caption">Fig.{n} — {fr.timestamp_str}</div>\n'
                    )
                return ""
            body = re.sub(r"\{IMAGE:(\d+)\}", _rep, body)
            body = re.sub(r"\{IMPORTANT\}(.*?)\{/IMPORTANT\}",
                          r'<div class="important-box">\1</div>', body, flags=re.DOTALL)
            body = re.sub(r"\{KNOWLEDGE\}(.*?)\{/KNOWLEDGE\}",
                          r'<div class="knowledge-box">\1</div>', body, flags=re.DOTALL)
            body = re.sub(r"\{WARNING\}(.*?)\{/WARNING\}",
                          r'<div class="warning-box">\1</div>', body, flags=re.DOTALL)
            parts.append(body)
            parts.append("<hr>")

        parts.append("</body></html>")

        out = output_dir / f"{_safe(title)}_full.html"
        out.write_text("\n".join(parts), encoding="utf-8")
        return out

def _safe(text: str, max_len: int = 40) -> str:
    return "".join(c if c.isalnum() or c in "_- " else "_" for c in text)[:max_len].strip()

def _tex_escape(text: str) -> str:
    specials = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
                "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
                "^": r"\^{}"}
    for k, v in specials.items():
        text = text.replace(k, v)
    return text
