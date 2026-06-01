# -*- coding: utf-8 -*-
"""LaTeX PDF lecture notes template with premium aesthetics."""

import time

def build_latex_prompt(title: str, duration_sec: float, uploader: str, transcript: str, chapters: list = None) -> str:
    """Builds the prompt asking the LLM to directly generate LaTeX code with a highly professional template."""
    chapters_info = ""
    if chapters:
        chapters_info = "\n视频章节:\n"
        for ch in chapters:
            t = ch.get("title", "")
            s = ch.get("start_time", 0)
            chapters_info += f"- [{s:.0f}s] {t}\n"

    # Truncate transcript to prevent context length explosion
    if len(transcript) > 8000:
        transcript = transcript[:8000] + "\n...(truncated)"
        
    date_str = time.strftime("%Y-%m-%d")

    return f"""请根据以下会议/视频内容，生成一份具有顶级学术期刊和商业报告质感的 LaTeX 文档。

会议标题: {title}
主讲人: {uploader}
时长: {duration_sec:.0f} 秒
{chapters_info}

内容转录:
{transcript}

要求:
1. 生成完整的 .tex 文档，从 \\documentclass 到 \\end{{document}}。
2. 必须原封不动地使用我下面提供的【LaTeX 模板头部】（这包含了所有美观的 tcolorbox 和 fancyhdr 设置）。
3. 知识结构重组：按逻辑分章节 (\\section, \\subsection)，而非按时间流水账。
4. 在正文中，大量且恰当地使用我定义的彩色盒子环境来强调内容：
   - \\begin{{importantbox}}{{核心决策/重点}} ... \\end{{importantbox}}
   - \\begin{{knowledgebox}}{{背景知识}} ... \\end{{knowledgebox}}
   - \\begin{{warningbox}}{{风险提示}} ... \\end{{warningbox}}
   - \\begin{{actionbox}}{{行动计划/待办}} ... \\end{{actionbox}}
5. 必须在文档开始处使用 \\maketitle 生成标题，接着使用 \\tableofcontents 生成目录，再使用 \\newpage 开启正文。
6. 图片插入：如果原文中包含 {{IMAGE:N}} 标记，请务必将其转换为严谨的 LaTeX 浮动体代码注入正文，例如：
   \\begin{{figure}}[H]
   \\centering
   \\includegraphics[width=0.8\\linewidth]{{image_N}}
   \\caption{{这里填写原有的图片说明}}
   \\end{{figure}}

请将以下模板头部与你生成的正文结合，输出完整的 LaTeX 代码（无需任何 Markdown 代码块包装，直接输出纯文本）：

\\documentclass[a4paper,11pt]{{article}}
\\usepackage[fontset=fandol]{{ctex}}
\\usepackage{{amsmath,amssymb,graphicx,geometry,listings,hyperref,booktabs,float,fancyhdr,tikz,xcolor}}
\\usepackage[most]{{tcolorbox}}
\\geometry{{margin=2.5cm}}

% 自定义彩色高亮框
\\newtcolorbox{{knowledgebox}}[1]{{enhanced,colback=blue!5!white,colframe=blue!75!black,colbacktitle=blue!75!black,coltitle=white,fonttitle=\\bfseries,title=#1,attach boxed title to top left={{yshift=-2mm,xshift=2mm}},boxrule=1pt,sharp corners}}
\\newtcolorbox{{importantbox}}[1]{{enhanced,colback=yellow!10!white,colframe=yellow!80!black,colbacktitle=yellow!80!black,coltitle=black,fonttitle=\\bfseries,title=#1,sharp corners}}
\\newtcolorbox{{warningbox}}[1]{{enhanced,colback=red!5!white,colframe=red!75!black,colbacktitle=red!75!black,coltitle=white,fonttitle=\\bfseries,title=#1,sharp corners}}
\\newtcolorbox{{actionbox}}[1]{{enhanced,colback=orange!5!white,colframe=orange!60!black,colbacktitle=orange!60!black,coltitle=white,fonttitle=\\bfseries,title=#1,sharp corners}}

% 代码块样式
\\lstset{{basicstyle=\\ttfamily\\small,breaklines=true,frame=single,keywordstyle=\\color{{blue}},stringstyle=\\color{{red!60!black}},commentstyle=\\color{{green!60!black}}}}

% 页眉页脚设置
\\pagestyle{{fancy}}
\\fancyhead[L]{{\\small \\textcolor{{gray}}{{ {title} }}}}
\\fancyhead[R]{{\\small \\textbf{{SmartMeet 智能纪要}}}}
\\fancyfoot[L]{{\\small \\textcolor{{gray}}{{日期: {date_str}}}}}
\\fancyfoot[C]{{\\small \\thepage}}
\\fancyfoot[R]{{\\small \\textcolor{{gray}}{{Powered by Agent Suite}}}}
\\renewcommand{{\\headrulewidth}}{{0.4pt}}
\\renewcommand{{\\footrulewidth}}{{0.4pt}}

\\title{{\\Huge\\bfseries {title}}}
\\author{{SmartMeet 自动生成 \\\\[0.5cm] \\small 讲者: {uploader}}}
\\date{{{date_str}}}

\\begin{{document}}
\\maketitle
\\tableofcontents
\\newpage

% 你的正文从这里开始
"""
