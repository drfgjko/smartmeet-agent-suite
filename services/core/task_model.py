# -*- coding: utf-8 -*-
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path

from utils.file_system import get_workspace_dir

# 将 smartmeet.db 统一放在工作区目录 (workspace/) 下
_DB_PATH = get_workspace_dir() / "smartmeet.db"
engine = create_engine(
    f"sqlite:///{_DB_PATH}", 
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TaskRecord(Base):
    """异步任务持久化表"""
    __tablename__ = "tasks"

    task_id = Column(String(50), primary_key=True, index=True)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    meeting_id = Column(String(50), index=True, nullable=True)
    result_json = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    
    # 强制在数据库中使用 UTC 时间以避免时区问题
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# 自动建表（如果表已存在则忽略）
Base.metadata.create_all(bind=engine)
