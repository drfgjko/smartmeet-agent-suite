# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import re
from pathlib import Path
from openai import OpenAI

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
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv("NOTEKING_LLM_BASE_URL") or "https://api.minimax.chat/v1"
        self.model = model or os.getenv("NOTEKING_LLM_MODEL") or "abab6.5s-chat"

    def generate_mindmap(self, text: str) -> str:
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        prompt = MINDMAP_PROMPT.format(text=text)
        
        response = client.chat.completions.create(
            model=self.model,
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
