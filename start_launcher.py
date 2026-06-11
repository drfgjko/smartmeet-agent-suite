
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

def _print_banner() -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()
        console.print()

        ascii_art = (
            "  ____                       _   __  __           _   \n"
            " / ___|_ __ ___   __ _ _ __| |_|  \\/  | ___  ___| |_ \n"
            " \\___ \\| '_ ` _ \\ / _` | '__| __|  \\/  |/ _ \\/ _ \\ __|\n"
            "  ___) | | | | | | (_| | |  | |_| |  | |  __/  __/ |_ \n"
            " |____/|_| |_| |_|\\__,_|_|   \\__|_|  |_|\\___|\\___|\\__|\n"
        )

        banner_text = Text()
        banner_text.append(ascii_art, style="bold cyan")
        banner_text.append("\n")
        banner_text.append("  SmartMeet\n\n", style="bold white")
        banner_text.append("  前端服务: ", style="green")
        banner_text.append("http://localhost:3000\n", style="underline bright_cyan")
        banner_text.append("  后端网关: ", style="green")
        banner_text.append("http://localhost:8000\n", style="underline bright_cyan")
        banner_text.append("  接口文档: ", style="green")
        banner_text.append("http://localhost:8000/docs\n", style="underline bright_cyan")
        banner_text.append("  后台计算: ", style="green")
        banner_text.append("ARQ Redis Worker\n\n", style="underline bright_yellow")
        banner_text.append("  即将在三个独立窗口中分别启动 前端、API 和计算节点...\n", style="dim")

        console.print(Panel(
            banner_text,
            title="[bold bright_white]SmartMeet Agent Suite[/]",
            border_style="cyan",
            expand=False,
            padding=(0, 2),
        ))
        console.print()

    except ImportError:

        print()
        print("=" * 60)
        print("  SmartMeet  ")
        print("=" * 60)
        print("  前端服务: http://localhost:3000")
        print("  后端网关: http://localhost:8000")
        print("  接口文档: http://localhost:8000/docs")
        print("  后台计算: ARQ Redis Worker")
        print("=" * 60)
        print()

def _check_prerequisites() -> bool:
    web_dir = PROJECT_ROOT / "frontend"
    if not web_dir.exists():
        print(f"[错误] 前端目录不存在: {web_dir}")
        return False

    node_modules = web_dir / "node_modules"
    if not node_modules.exists():
        print("[错误] 前端依赖未安装，请先在 frontend/ 目录下执行: npm install")
        return False

    api_main = PROJECT_ROOT / "interfaces" / "api" / "main.py"
    if not api_main.exists():
        print(f"[错误] 后端入口不存在: {api_main}")
        return False

    return True

import platform

IS_WINDOWS = sys.platform == "win32"

def _build_window_cmd(title: str, work_dir: Path, command: str) -> str:
    inner_cmd = f'chcp 65001 >nul & set PYTHONIOENCODING=utf-8 & cd /d "{work_dir}" & {command}'
    return f'start "{title}" cmd /k "{inner_cmd}"'

def _launch_frontend() -> subprocess.Popen | None:
    print("[1/2] 正在启动前端服务 (Next.js)...")
    web_dir = PROJECT_ROOT / "frontend"
    if IS_WINDOWS:
        cmd = _build_window_cmd("SmartMeet Frontend - Next.js", web_dir, "npm run dev")
        subprocess.run(cmd, shell=True, cwd=str(PROJECT_ROOT))
        return None
    else:

        return subprocess.Popen(["npm", "run", "dev"], cwd=str(web_dir))

def _launch_backend() -> subprocess.Popen | None:
    print("[2/3] 正在启动后端网关 (FastAPI)...")
    backend_command = "conda run --no-capture-output -n smartmeet python -m interfaces.api.main"
    if IS_WINDOWS:
        cmd = _build_window_cmd("SmartMeet Backend - FastAPI", PROJECT_ROOT, backend_command)
        subprocess.run(cmd, shell=True, cwd=str(PROJECT_ROOT))
        return None
    else:

        return subprocess.Popen(backend_command, shell=True, cwd=str(PROJECT_ROOT))

def _launch_worker() -> subprocess.Popen | None:
    print("[3/3] 正在启动后台计算节点 (ARQ Worker)...")
    worker_command = "conda run --no-capture-output -n smartmeet arq workers.arq_worker.WorkerSettings"
    if IS_WINDOWS:
        cmd = _build_window_cmd("SmartMeet Worker - ARQ Redis", PROJECT_ROOT, worker_command)
        subprocess.run(cmd, shell=True, cwd=str(PROJECT_ROOT))
        return None
    else:
        return subprocess.Popen(worker_command, shell=True, cwd=str(PROJECT_ROOT))

def main() -> None:
    os.environ["PYTHONIOENCODING"] = "utf-8"

    _print_banner()

    if not _check_prerequisites():
        print()
        print("启动中止，请修复上述问题后重试。")
        input("按回车键退出...")
        sys.exit(1)

    import time

    fe_proc = _launch_frontend()
    time.sleep(1.5)  
    be_proc = _launch_backend()
    time.sleep(1.5)
    worker_proc = _launch_worker()

    print()
    if IS_WINDOWS:
        print("所有服务已在独立窗口中启动！")
        print("  - 窗口 1: SmartMeet Frontend - Next.js")
        print("  - 窗口 2: SmartMeet Backend - FastAPI")
        print("  - 窗口 3: SmartMeet Worker - ARQ Redis")
        print()
        print("本窗口将在 3 秒后自动关闭...")
        import time
        time.sleep(3)
    else:
        print("所有服务已启动！按 Ctrl+C 可停止所有服务。")
        print("-" * 60)
        try:

            if be_proc:
                be_proc.wait()
            elif fe_proc:
                fe_proc.wait()
        except KeyboardInterrupt:
            print("\n正在关闭服务...")
            if fe_proc:
                fe_proc.terminate()
            if be_proc:
                be_proc.terminate()
            if worker_proc:
                worker_proc.terminate()
            print("清理完毕，再见！")

if __name__ == "__main__":
    main()
