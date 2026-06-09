# -*- coding: utf-8 -*-
"""
一键迁移脚手架：将历史数据的 Markdown 思维导图批量转换为 HTML 网页脑图
避免重新跑满长视频流水线！
"""
import json
import re
from pathlib import Path

def migrate_mindmaps(base_dir: Path):
    if not base_dir.exists():
        print(f"目录不存在: {base_dir}")
        return

    count = 0
    # 遍历所有 final_result.json
    for result_file in base_dir.rglob("final_result.json"):
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            output_files = data.get("output_files", {})
            mindmap_path_str = output_files.get("mindmap", "")
            
            if mindmap_path_str:
                meeting_dir = result_file.parent
                # 如果 mindmap 已经被改成了 html，我们要找回 md 文件
                if mindmap_path_str.endswith(".html"):
                    md_path_str = mindmap_path_str[:-5] + ".md"
                    md_file = meeting_dir / Path(md_path_str).name
                    html_path_str = mindmap_path_str
                else:
                    md_path_str = mindmap_path_str
                    md_file = meeting_dir / Path(md_path_str).name
                    html_path_str = mindmap_path_str[:-3] + ".html"
                
                if not md_file.exists():
                    print(f"[Warning] Cannot find mindmap file: {md_file}")
                    continue
                
                # 1. 提取原始 Mermaid 代码
                content = md_file.read_text(encoding="utf-8")
                match = re.search(r"```mermaid\s*(.*?)\s*```", content, re.DOTALL)
                if not match:
                    mindmap_code = content.replace("# 会议思维导图", "").strip()
                else:
                    mindmap_code = match.group(1).strip()
                
                # 2. 组装 HTML 模板 (含导出 PNG)
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
                
                # 3. 写入新的 .html 文件
                html_file = md_file.with_suffix(".html")
                html_file.write_text(html_content, encoding="utf-8")
                
                # 4. 更新 result.json 里的路径记录，恢复双轨
                data["output_files"]["mindmap"] = md_path_str
                data["output_files"]["mindmap_html"] = html_path_str
                
                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                print(f"[Success] Dual-track Migrated: {meeting_dir.name}")
                count += 1
                
        except Exception as e:
            print(f"[Error] Failed to process {result_file}: {e}")

if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    demo_dir = project_root / "interfaces" / "web" / "public" / "demos"
    reports_dir = project_root / "reports"
    
    print("Scanning frontend Demos...")
    migrate_mindmaps(demo_dir)
    
    print("\nScanning backend Reports...")
    migrate_mindmaps(reports_dir)
    
    print("\nMigration completed. Please hard refresh the frontend page.")
