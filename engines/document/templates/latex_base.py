# -*- coding: utf-8 -*-
"""LaTeX PDF lecture notes template static variables."""

LATEX_PREAMBLE = r"""\documentclass[a4paper,11pt]{article}
\usepackage[fontset=fandol]{ctex}
\usepackage{amsmath,amssymb,graphicx,geometry,listings,hyperref,booktabs,float,fancyhdr,tikz,xcolor}
\usepackage[most]{tcolorbox}
\geometry{margin=2.5cm}

% 自定义彩色高亮框
\newtcolorbox{knowledgebox}[1]{enhanced,colback=blue!5!white,colframe=blue!75!black,colbacktitle=blue!75!black,coltitle=white,fonttitle=\bfseries,title=#1,attach boxed title to top left={yshift=-2mm,xshift=2mm},boxrule=1pt,sharp corners}
\newtcolorbox{importantbox}[1]{enhanced,colback=yellow!10!white,colframe=yellow!80!black,colbacktitle=yellow!80!black,coltitle=black,fonttitle=\bfseries,title=#1,sharp corners}
\newtcolorbox{warningbox}[1]{enhanced,colback=red!5!white,colframe=red!75!black,colbacktitle=red!75!black,coltitle=white,fonttitle=\bfseries,title=#1,sharp corners}
\newtcolorbox{actionbox}[1]{enhanced,colback=orange!5!white,colframe=orange!60!black,colbacktitle=orange!60!black,coltitle=white,fonttitle=\bfseries,title=#1,sharp corners}

% 代码块样式
\lstset{basicstyle=\ttfamily\small,breaklines=true,frame=single,keywordstyle=\color{blue},stringstyle=\color{red!60!black},commentstyle=\color{green!60!black}}

% 页眉页脚设置
\pagestyle{fancy}
\fancyhead[L]{\small \textcolor{gray}{{ {title} }}}
\fancyhead[R]{\small \textbf{SmartMeet 智能纪要}}
\fancyfoot[L]{\small \textcolor{gray}{日期: {date_str}}}
\fancyfoot[C]{\small \thepage}
\fancyfoot[R]{\small \textcolor{gray}{Powered by Agent Suite}}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0.4pt}

\title{\Huge\bfseries {title}}
\author{SmartMeet 自动生成 \\[0.5cm] \small 讲者: {uploader}}
\date{{date_str}}

\begin{document}
\maketitle
\tableofcontents
\newpage
"""

LATEX_POSTAMBLE = r"""
\end{document}
"""
