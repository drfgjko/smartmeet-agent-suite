#!/bin/bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

if ! command -v conda &> /dev/null; then
    if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/miniconda3/etc/profile.d/conda.sh"
    elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/anaconda3/etc/profile.d/conda.sh"
    else
        echo "[错误] 未找到 conda 命令，请确保已安装 Miniconda/Anaconda 并已加入环境变量。"
        exit 1
    fi
fi

conda run --no-capture-output -n smartmeet python "$PROJECT_ROOT/start_launcher.py" "$@"
