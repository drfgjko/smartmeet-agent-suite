#!/bin/bash

# SmartMeet Agent Suite - 一键启动脚本 (macOS / Linux)

set -e

# 项目根目录（脚本所在目录）
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

cat << "EOF"

 ========================================================================

  ███████ ███    ███  █████  ██████  ████████ ███    ███ ███████ ███████ ████████
  ██      ████  ████ ██   ██ ██   ██    ██    ████  ████ ██      ██         ██   
  ███████ ██ ████ ██ ███████ ██████     ██    ██ ████ ██ █████   █████      ██   
       ██ ██      ██ ██   ██ ██   ██    ██    ██      ██ ██      ██         ██   
  ███████ ██      ██ ██   ██ ██   ██    ██    ██      ██ ███████ ███████    ██   

 ========================================================================

  欢迎使用 SmartMeet 多模态智能会议协同 Agent 解决方案

EOF

# 检查 conda 是否可用
if ! command -v conda &> /dev/null; then
    # 尝试加载可能的用户 conda 环境
    if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/miniconda3/etc/profile.d/conda.sh"
    elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/anaconda3/etc/profile.d/conda.sh"
    else
        echo "[错误] 未找到 conda 命令，请确保已安装 Miniconda/Anaconda 并已加入环境变量。"
        exit 1
    fi
fi

# 启动 Python 编排器
conda run --no-capture-output -n smartmeet python "$PROJECT_ROOT/start_launcher.py" "$@"
