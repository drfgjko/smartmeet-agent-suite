from __future__ import annotations

import os
import sys
import json
import shutil
from pathlib import Path
import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from dotenv import load_dotenv

# 加载 .env 配置文件
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# 强制将标准输出/错误重构为 UTF-8 编码，防止 Windows GBK 终端环境或重定向时发生乱码/崩溃
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()

API_BASE = os.environ.get("SMARTMEET_API", "http://127.0.0.1:8000")

@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="1.0.0", prog_name="smartmeet")
def main(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-c", "--context", default=None, help="内容描述（例如：AI开源项目讨论）")
@click.option("--speakers", default=None, type=int, help="说话人数（不传则自动检测）")
@click.option("--denoise", default=1, type=int, help="降噪级别（0-3）")
@click.option("-o", "--output", default=None, help="结果保存目录")
@click.option("--config", default=None, help="JobConfig JSON 字符串或本地 JSON 文件路径")
def process(files, context, speakers, denoise, output, config):
    console.print(Panel(
        f"[bold cyan]SmartMeet CLI[/bold cyan] - 录音处理客户端\n"
        f"文件: {', '.join(str(f) for f in files)}\n"
        f"API 地址: {API_BASE}",
        title="离线流水线启动",
    ))

    target_file = Path(files[0])
    if len(files) > 1:
        console.print(f"[bold yellow]提示：当前上传仅支持单文件，将处理第一个: {target_file.name}[/bold yellow]")

    file_id = None
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task(f"正在上传 {target_file.name} 至 API 服务器...", total=None)
        try:
            upload_url = f"{API_BASE}/api/v1/recording/upload"
            with open(target_file, "rb") as f:
                r = httpx.post(upload_url, files={"file": (target_file.name, f, "application/octet-stream")})
            if r.status_code != 200:
                raise Exception(f"上传失败: HTTP {r.status_code} - {r.text}")
            file_id = r.json().get("file_id")
            progress.update(task, description=f"上传完成! 文件 ID: {file_id}")
        except Exception as e:
            progress.update(task, description=f"[red]上传错误: {e}[/red]")
            sys.exit(1)

    _run_process_stream(
        file_id=file_id,
        context=context,
        speakers=speakers,
        denoise=denoise,
        output=output,
        config=config,
    )

@main.command()
@click.argument("url")
@click.option("-c", "--context", default=None, help="内容描述或补充上下文")
@click.option("-o", "--output", default=None, help="结果保存目录")
@click.option("--config", default=None, help="JobConfig JSON 字符串或本地 JSON 文件路径")
def run(url, context, output, config):
    console.print(Panel(
        f"[bold cyan]SmartMeet CLI[/bold cyan] - 视频链接处理客户端\n"
        f"链接: {url}\n"
        f"API 地址: {API_BASE}",
        title="链接处理启动",
    ))

    _run_process_stream(
        url=url,
        context=context,
        output=output,
        config=config,
    )

def _run_process_stream(file_id=None, url=None, context=None, speakers=None, denoise=1, output=None, config=None):
    import time
    start_time = time.time()
    payload = {
        "denoise_level": denoise,
    }
    if file_id:
        payload["file_id"] = file_id
    if url:
        payload["url"] = url
    if context:
        payload["context"] = context
    if speakers is not None:
        payload["num_speakers"] = speakers

    if config:
        config_path = Path(config)
        if config_path.exists() and config_path.is_file():
            try:
                payload["job_config"] = config_path.read_text(encoding="utf-8")
            except Exception as e:
                console.print(f"[yellow]无法读取配置文件 {config_path}: {e}[/yellow]")
        else:
            payload["job_config"] = config

    process_url = f"{API_BASE}/api/v1/recording/process/stream"
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("正在连接流水线...", total=None)
        try:
            with httpx.stream("POST", process_url, data=payload, timeout=None) as resp:
                if resp.status_code != 200:
                    resp.read() # 读取错误信息
                    raise Exception(f"流水线启动失败: HTTP {resp.status_code} - {resp.text}")

                meeting_id = None
                content = None
                output_files = {}

                for line in resp.iter_lines():
                    if not line:
                        continue
                    decoded = line.strip()
                    if decoded.startswith("data: "):
                        ev = json.loads(decoded[6:])
                        stage = ev.get("stage")
                        msg = ev.get("message", "处理中...")

                        if stage == "done":
                            meeting_id = ev.get("meeting_id")
                            content = ev.get("content")
                            output_files = ev.get("output_files", {})
                            errors = ev.get("errors", [])
                            progress.update(task, description="完成!")
                        elif stage == "error":
                            raise Exception(ev.get("message", "未知错误"))
                        else:
                            stage_map = {
                                "started": "启动",
                                "preprocess": "媒体预处理",
                                "transcribe": "语音转录",
                                "diarize": "角色识别",
                                "keyframes": "关键帧",
                                "agent_running": "智能分析"
                            }
                            cn_stage = stage_map.get(stage, stage)
                            progress.update(task, description=f"[[cyan]{cn_stage}[/cyan]] {msg}")

            if not content:
                raise Exception("流水线完成但未返回任何内容")

            elapsed = time.time() - start_time
            if elapsed >= 60:
                time_str = f"{int(elapsed // 60)} 分 {int(elapsed % 60)} 秒"
            else:
                time_str = f"{elapsed:.1f} 秒"

            console.print()
            console.print(Panel(
                f"[bold green]处理完成![/bold green]\n"
                f"会议 ID: {meeting_id}\n"
                f"生成报告长度: {len(content)} 字符。\n"
                f"总共用时: {time_str}",
                title="结果摘要"
            ))

            if errors:
                console.print(Panel("\n".join(f"- {err}" for err in errors), title="[bold red]执行过程中出现非致命错误[/bold red]", border_style="red"))
            elif "pdf" not in output_files or not output_files["pdf"]:
                console.print(Panel("- 未生成 PDF 资产，可能是由于系统缺失依赖导致降级失败。请检查服务端日志。", title="[bold yellow]产出缺失警告[/bold yellow]", border_style="yellow"))

            if output:
                out_path = Path(output)
                out_path.mkdir(parents=True, exist_ok=True)

                # 使用服务端返回的原始文件名，这样能保留标题和区分 mindmap
                title = ev.get("title", "")
                import re
                safe_title = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', title).strip().strip("_") if title else ""
                safe_title = safe_title[:50].strip()
                filename_base = f"{meeting_id}_{safe_title}" if safe_title else meeting_id

                md_file = out_path / f"{filename_base}.md"
                md_file.write_text(content, encoding="utf-8")
                console.print(f"[green]已保存 Markdown 报告至: {md_file}[/green]")

                fmt_map = {
                    "pdf": "PDF 讲义",
                    "html": "HTML 网页",
                    "mindmap": "思维导图",
                    "markdown": "Markdown 文档",
                    "transcript": "转录文本"
                }
                for fmt, src_path_str in output_files.items():
                    if fmt != "markdown" and src_path_str:
                        src_path = Path(src_path_str)
                        if src_path.exists():
                            # 保留源文件的名称（源文件名已由服务端妥善处理好）
                            dst_path = out_path / src_path.name
                            shutil.copy(src_path, dst_path)
                            cn_fmt = fmt_map.get(fmt, fmt)
                            console.print(f"[green]已保存 {cn_fmt} 资产至: {dst_path}[/green]")
            else:
                console.print("\n[bold]输出路径（服务端）:[/bold]")
                fmt_map = {
                    "pdf": "PDF 讲义",
                    "html": "HTML 网页",
                    "mindmap": "思维导图",
                    "markdown": "Markdown 文档",
                    "transcript": "转录文本"
                }
                for fmt, path in output_files.items():
                    cn_fmt = fmt_map.get(fmt, fmt)
                    console.print(f"  [{cn_fmt}] {path}")

        except Exception as e:
            progress.update(task, description=f"[red]错误: {e}[/red]")
            console.print(f"\n[red]流水线处理失败:[/red] {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()