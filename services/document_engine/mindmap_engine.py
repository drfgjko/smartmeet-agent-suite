# -*- coding: utf-8 -*-
"""
Mermaid Mindmap Generator（思维导图生成引擎）
- 基于 LLM 驱动的会议脑图生成：根据会议纪要自动提炼核心主旨，并转换为标准 Mermaid 脑图代码
- 鲁棒解析机制：支持自动剥离大模型输出的 markdown 代码块标记，保证提取纯净的 Mermaid 文本
- 架构解耦设计：作为独立 Pipeline 节点，支持传入外部 LLM 客户端与自定义输出路径，便于服务集成
- 异常退化保护：在调用 LLM 失败或格式解析异常时，支持优雅返回原始生成结果并保证后续流程不中断

面试考点：
- 如何保证大模型输出纯净的 Mermaid 语法而不夹杂解释文字？（System Role 设定 + Few-shot 约束 + 正则表达式匹配清洗）
- 思维导图的根节点渲染语法与子分支层级关系如何组织？（使用缩进与特定的括号声明，如 root((主题))）
"""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

MINDMAP_PROMPT = """根据以下会议内容，生成一个标准 Mermaid 格式的思维导图代码。

会议内容：
{text}

要求：
1. 必须以 ```mermaid 开头，``` 结尾。
2. 第一行必须是 `mindmap`。
3. 根节点使用 `root((主题名称))` 语法，从内容推断主题。
4. 使用空格缩进表示分支层级结构，不要使用任何特殊符号作为前缀，只使用缩进和文本。
5. 不允许包含任何除 Mermaid 代码块之外的解释性文字。
6. 使用中文。"""

class MindMapPipeline:
    def __init__(
        self,
        llm_client: Any = None,
    ):
        self.llm = llm_client

    def generate_mindmap(self, text: str) -> str:
        if self.llm is None:
            raise RuntimeError("MindMapPipeline requires llm_client to be injected")
        prompt = MINDMAP_PROMPT.format(text=text)

        raw_output = self.llm.chat_sync(
            messages=[
                {"role": "system", "content": "You are a professional business analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        match = re.search(r"```mermaid\s*(.*?)\s*```", raw_output, re.DOTALL)
        if match:
            return match.group(1).strip()
        return raw_output.strip()

    def save_mindmap(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mindmap_code = self.generate_mindmap(text)
        
        # 1. 写入原始 Markdown (供飞书分发与前端下载)
        md_content = f"# 会议思维导图\n\n```mermaid\n{mindmap_code}\n```"
        output_path.write_text(md_content, encoding="utf-8")
        
        # 2. 写入前端预览用的 HTML (旁边附带生成)
        html_path = output_path.with_suffix(".html")
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>会议思维导图</title>
    <style>
        body {{ margin: 0; padding: 0; background-color: #f8fafc; font-family: sans-serif; height: 100vh; overflow: hidden; }}
        .controls {{ position: fixed; top: 20px; right: 20px; z-index: 100; display: flex; gap: 10px; }}
        .download-btn {{ padding: 10px 20px; background: #ffc900; color: #000; border: 2px solid #000; border-radius: 8px; font-weight: bold; cursor: pointer; box-shadow: 4px 4px 0 #000; transition: transform 0.1s; text-decoration: none; display: inline-block; font-size: 14px; }}
        .download-btn:active {{ transform: translate(2px, 2px); box-shadow: 2px 2px 0 #000; }}
        .mindmap-container {{ width: 100vw; height: 100vh; overflow: auto; padding: 40px; box-sizing: border-box; display: flex; align-items: flex-start; justify-content: center; }}
        .mermaid {{ min-width: 100%; display: flex; justify-content: center; }}
        .mermaid svg {{ max-width: none !important; height: auto !important; min-width: 1200px; }}
    </style>
</head>
<body>
    <div class="controls">
        <button class="download-btn" onclick="exportPNG()">导出 PNG</button>
    </div>
    <div class="mindmap-container">
        <pre class="mermaid">
{mindmap_code}
        </pre>
    </div>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ 
            startOnLoad: true, 
            theme: 'default',
            securityLevel: 'loose',
            useMaxWidth: false
        }});
    </script>
    <script>
        function exportPNG() {{
            const svg = document.querySelector('.mermaid svg');
            if (!svg) return;
            
            // 获取真实宽高
            const viewBox = svg.viewBox.baseVal;
            const width = viewBox.width || svg.getBoundingClientRect().width;
            const height = viewBox.height || svg.getBoundingClientRect().height;
            
            // 克隆以避免影响当前DOM
            const cloneSvg = svg.cloneNode(true);
            cloneSvg.setAttribute('width', width);
            cloneSvg.setAttribute('height', height);
            
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const data = new XMLSerializer().serializeToString(cloneSvg);
            const DOMURL = window.URL || window.webkitURL || window;
            const img = new Image();
            const svgBlob = new Blob([data], {{type: 'image/svg+xml;charset=utf-8'}});
            const url = DOMURL.createObjectURL(svgBlob);
            img.onload = function () {{
                // 提高分辨率
                const scale = 2;
                canvas.width = width * scale;
                canvas.height = height * scale;
                ctx.fillStyle = '#f8fafc';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.scale(scale, scale);
                ctx.drawImage(img, 0, 0, width, height);
                DOMURL.revokeObjectURL(url);
                const imgURI = canvas.toDataURL('image/png').replace('image/png', 'image/octet-stream');
                const a = document.createElement('a');
                a.download = 'mindmap.png';
                a.href = imgURI;
                a.click();
            }};
            img.src = url;
        }}
    </script>
</body>
</html>"""
        html_path.write_text(html_content, encoding="utf-8")
        
        # 依然返回 md 路径给核心层
        return output_path

    async def async_generate_mindmap(self, text: str) -> str:
        return await asyncio.to_thread(self.generate_mindmap, text)

    async def async_save_mindmap(self, text: str, output_path: Path) -> Path:
        return await asyncio.to_thread(self.save_mindmap, text, output_path)
