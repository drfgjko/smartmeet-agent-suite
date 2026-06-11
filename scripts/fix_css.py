import json
import re
from pathlib import Path

demo_dir = Path('frontend/public/demos')
for md_file in demo_dir.rglob('*_mindmap.md'):
    content = md_file.read_text(encoding='utf-8')
    match = re.search(r'```mermaid\s*(.*?)\s*```', content, re.DOTALL)
    mindmap_code = match.group(1).strip() if match else content.replace('# 会议思维导图', '').strip()

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>会议思维导图</title>
    <style>
        body {{ margin: 0; padding: 0; background-color: #f8fafc; font-family: sans-serif; height: 100vh; overflow: hidden; }}
        .controls {{ position: fixed; top: 20px; right: 20px; z-index: 100; }}
        .download-btn {{ padding: 10px 20px; background: #4ade80; color: #000; border: 2px solid #000; border-radius: 8px; font-weight: bold; cursor: pointer; box-shadow: 4px 4px 0 #000; transition: transform 0.1s; text-decoration: none; display: inline-block; }}
        .download-btn:active {{ transform: translate(2px, 2px); box-shadow: 2px 2px 0 #000; }}
        .mindmap-container {{ width: 100vw; height: 100vh; overflow: auto; padding: 40px; box-sizing: border-box; display: flex; align-items: flex-start; justify-content: center; }}
        .mermaid {{ min-width: 100%; display: flex; justify-content: center; }}
        .mermaid svg {{ max-width: none !important; height: auto !important; min-width: 1200px; }}
    </style>
</head>
<body>
    <div class="controls">
        <button class="download-btn" onclick="window.print()">Print / Export PDF</button>
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
</body>
</html>"""
    html_file = md_file.with_suffix('.html')
    html_file.write_text(html_content, encoding='utf-8')
    print(f'Updated {html_file}')
