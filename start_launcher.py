# -*- coding: utf-8 -*-
"""
SmartMeet Agent Suite - Python 启动编排器

职责：
1. 打印 Rich 横幅（完美控制编码和终端能力检测）
2. 分别启动前端和后端两个独立的 cmd 窗口
3. 每个子窗口内正确设置编码环境（chcp 65001 + PYTHONIOENCODING）
4. 提供友好的错误提示
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ── 项目根目录 ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent


def _print_banner() -> None:
    """使用 Rich 打印启动横幅，终端不支持时自动降级为纯文本。"""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()
        console.print()

        # 构建 ASCII Art 标题
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
        banner_text.append("  多模态智能会议协同 Agent 解决方案\n\n", style="bold white")
        banner_text.append("  前端服务: ", style="green")
        banner_text.append("http://localhost:3000\n", style="underline bright_cyan")
        banner_text.append("  后端服务: ", style="green")
        banner_text.append("http://localhost:8000\n", style="underline bright_cyan")
        banner_text.append("  接口文档: ", style="green")
        banner_text.append("http://localhost:8000/docs\n\n", style="underline bright_cyan")
        banner_text.append("  即将在两个独立窗口中分别启动前端和后端服务...\n", style="dim")

        console.print(Panel(
            banner_text,
            title="[bold bright_white]SmartMeet Agent Suite[/]",
            border_style="cyan",
            expand=False,
            padding=(0, 2),
        ))
        console.print()

    except ImportError:
        # rich 库不可用时，使用纯文本降级输出
        print()
        print("=" * 60)
        print("  SmartMeet Agent Suite")
        print("  多模态智能会议协同 Agent 解决方案")
        print("=" * 60)
        print("  前端服务: http://localhost:3000")
        print("  后端服务: http://localhost:8000")
        print("  接口文档: http://localhost:8000/docs")
        print("=" * 60)
        print()


def _check_prerequisites() -> bool:
    """检查启动前置条件，返回 False 表示不满足。"""
    web_dir = PROJECT_ROOT / "web"
    if not web_dir.exists():
        print(f"[错误] 前端目录不存在: {web_dir}")
        return False

    node_modules = web_dir / "node_modules"
    if not node_modules.exists():
        print("[错误] 前端依赖未安装，请先在 web/ 目录下执行: npm install")
        return False

    api_main = PROJECT_ROOT / "api" / "main.py"
    if not api_main.exists():
        print(f"[错误] 后端入口不存在: {api_main}")
        return False

    return True


import platform

IS_WINDOWS = sys.platform == "win32"

def _build_window_cmd(title: str, work_dir: Path, command: str) -> str:
    """构建在新 cmd 窗口中执行的命令字符串（仅限 Windows）。"""
    inner_cmd = f'chcp 65001 >nul & set PYTHONIOENCODING=utf-8 & cd /d "{work_dir}" & {command}'
    return f'start "{title}" cmd /k "{inner_cmd}"'

def _launch_frontend() -> subprocess.Popen | None:
    """启动前端 Next.js 开发服务器。"""
    print("[1/2] 正在启动前端服务 (Next.js)...")
    web_dir = PROJECT_ROOT / "web"
    if IS_WINDOWS:
        cmd = _build_window_cmd("SmartMeet Frontend - Next.js", web_dir, "npm run dev")
        subprocess.run(cmd, shell=True, cwd=str(PROJECT_ROOT))
        return None
    else:
        # Unix 系统：作为子进程启动，日志混合输出或稍后处理
        return subprocess.Popen(["npm", "run", "dev"], cwd=str(web_dir))

def _launch_backend() -> subprocess.Popen | None:
    """启动后端 FastAPI 服务。"""
    print("[2/2] 正在启动后端服务 (FastAPI)...")
    backend_command = "conda run --no-capture-output -n smartmeet python -m api.main"
    if IS_WINDOWS:
        cmd = _build_window_cmd("SmartMeet Backend - FastAPI", PROJECT_ROOT, backend_command)
        subprocess.run(cmd, shell=True, cwd=str(PROJECT_ROOT))
        return None
    else:
        # Unix 系统：以 shell 方式运行
        return subprocess.Popen(backend_command, shell=True, cwd=str(PROJECT_ROOT))

def main() -> None:
    """主入口：打印横幅 -> 检查前置条件 -> 启动服务。"""
    os.environ["PYTHONIOENCODING"] = "utf-8"

    _print_banner()

    if not _check_prerequisites():
        print()
        print("启动中止，请修复上述问题后重试。")
        input("按回车键退出...")
        sys.exit(1)

    fe_proc = _launch_frontend()
    be_proc = _launch_backend()

    print()
    if IS_WINDOWS:
        print("所有服务已在独立窗口中启动！")
        print("  - 前端窗口: SmartMeet Frontend - Next.js")
        print("  - 后端窗口: SmartMeet Backend - FastAPI")
        print()
        print("本窗口将在 3 秒后自动关闭...")
        import time
        time.sleep(3)
    else:
        print("所有服务已启动！按 Ctrl+C 可停止所有服务。")
        print("-" * 60)
        try:
            # 阻塞等待后端进程结束
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
            print("清理完毕，再见！")

if __name__ == "__main__":
    main()
