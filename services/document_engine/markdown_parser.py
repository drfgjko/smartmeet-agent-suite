# -*- coding: utf-8 -*-
import re

class MarkdownToLatexConverter:
    """
    轻量级且严谨的纯 Python Markdown -> LaTeX 转换器。
    专门适配 ReportComposer 的自定义标签 {IMPORTANT}...{/IMPORTANT} 等。
    """
    
    def convert(self, md_content: str) -> str:
        # 第一步：正则替换大模型输出的高级组件标签
        def replace_box(match):
            box_type = match.group(1).lower()
            content = match.group(2).strip()
            
            env_map = {
                "important": "importantbox",
                "knowledge": "knowledgebox",
                "warning": "warningbox",
                "action": "actionbox"
            }
            
            title_map = {
                "importantbox": "核心重点",
                "knowledgebox": "知识补充",
                "warningbox": "风险提示",
                "actionbox": "行动指南"
            }
            
            latex_env = env_map.get(box_type, "importantbox")
            title = title_map[latex_env]
            
            # 使用 LaTeX 的环境替换
            return f"\n\\begin{{{latex_env}}}{{{title}}}\n{content}\n\\end{{{latex_env}}}\n"

        # 匹配 {IMPORTANT}文本{/IMPORTANT} 跨多行，兼容没有闭合标签的情况（遇到空行或文件末尾截断）
        md_content = re.sub(
            r'\{([A-Z]+)\}(.*?)(?:\{/\1\}|(?=\n\s*\n|\Z))', 
            replace_box, 
            md_content, 
            flags=re.DOTALL
        )
        
        lines = md_content.split('\n')
        tex_lines = []
        
        in_itemize = False
        in_enumerate = False
        
        def close_lists():
            nonlocal in_itemize, in_enumerate
            if in_itemize:
                tex_lines.append("\\end{itemize}")
                in_itemize = False
            if in_enumerate:
                tex_lines.append("\\end{enumerate}")
                in_enumerate = False

        for line in lines:
            line = line.strip()
            
            if not line:
                close_lists()
                tex_lines.append("")
                continue
                
            # 如果是刚刚正则替换好的 LaTeX 环境标记，原样保留
            if line.startswith("\\begin{") or line.startswith("\\end{"):
                close_lists()
                tex_lines.append(line)
                continue
                
            # 识别标题
            if line.startswith("#"):
                close_lists()
                heading_level = len(line) - len(line.lstrip('#'))
                heading_text = line.lstrip('#').strip()
                heading_text = heading_text.replace("**", "")
                
                if heading_level == 1:
                    tex_lines.append(f"\\section{{{heading_text}}}")
                elif heading_level == 2:
                    tex_lines.append(f"\\subsection{{{heading_text}}}")
                else:
                    tex_lines.append(f"\\subsubsection{{{heading_text}}}")
                continue
            
            # 处理列表
            list_match = re.match(r'^[\-\*]\s+(.*)', line)
            if list_match:
                if not in_itemize:
                    close_lists()
                    tex_lines.append("\\begin{itemize}")
                    in_itemize = True
                content = self._inline_parse(list_match.group(1))
                tex_lines.append(f"    \\item {content}")
                continue
                
            num_match = re.match(r'^\d+\.\s+(.*)', line)
            if num_match:
                if not in_enumerate:
                    close_lists()
                    tex_lines.append("\\begin{enumerate}")
                    in_enumerate = True
                content = self._inline_parse(num_match.group(1))
                tex_lines.append(f"    \\item {content}")
                continue
                
            # 处理非列表内容
            close_lists()
            
            # 图片匹配 {IMAGE:N}
            img_match = re.match(r'\{IMAGE:(\d+)\}', line)
            if img_match:
                idx = img_match.group(1)
                tex_lines.append("\\begin{figure}[H]")
                tex_lines.append("\\centering")
                tex_lines.append(f"\\includegraphics[width=0.8\\linewidth]{{image_{idx}}}")
                tex_lines.append("\\end{figure}")
                continue
                
            # 常规文本
            tex_lines.append(self._inline_parse(line))
            
        close_lists()
        return "\n".join(tex_lines)
        
    def _inline_parse(self, text: str) -> str:
        # 转义 LaTeX 特殊字符
        text = text.replace("&", "\\&").replace("%", "\\%").replace("$", "\\$").replace("#", "\\#")
        # 粗体 **xxx** -> \textbf{xxx}
        text = re.sub(r'\*\*(.*?)\*\*', r'\\textbf{\1}', text)
        return text
