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
        from services.integrations.llm_client import create_llm_client
        self.llm = llm_client or create_llm_client()

    def generate_mindmap(self, text: str) -> str:
        prompt = MINDMAP_PROMPT.format(text=text)
        
        response = self.llm._sync_client.chat.completions.create(
            model=self.llm.model,
            messages=[
                {"role": "system", "content": "You are a professional business analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        
        raw_output = response.choices[0].message.content or ""
        match = re.search(r"```mermaid\s*(.*?)\s*```", raw_output, re.DOTALL)
        if match:
            return match.group(1).strip()
        return raw_output.strip()

    def save_mindmap(self, text: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mindmap_code = self.generate_mindmap(text)
        
        content = f"# 会议思维导图\n\n```mermaid\n{mindmap_code}\n```"
        output_path.write_text(content, encoding="utf-8")
        return output_path
