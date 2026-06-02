# -*- coding: utf-8 -*-
"""
文件系统工具集合
"""
from pathlib import Path


def find_project_root() -> Path:
    """
    向上查找包含 pyproject.toml 的目录作为项目根目录
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    # 默认退后两层（如果 utils 位于根目录下，那就是上一层）
    return current.parent.parent
