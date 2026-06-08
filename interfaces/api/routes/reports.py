# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
import json
import shutil
from loguru import logger

from utils.file_system import get_reports_dir

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

REPORTS_DIR = get_reports_dir()

@router.get("")
async def list_reports():
    """获取历史报告列表"""
    if not REPORTS_DIR.exists():
        return []
        
    reports = []
    for d in REPORTS_DIR.iterdir():
        if d.is_dir():
            meeting_id = d.name
            final_result_path = d / "final_result.json"
            
            # 基础信息 fallback，通过创建时间戳获取排序依据
            report_info = {
                "meeting_id": meeting_id,
                "title": f"会议报告 - {meeting_id}",
                "status": "PROCESSING",
                "duration": 0,
                "num_speakers": 0,
                "created_at": int(d.stat().st_ctime * 1000)
            }
            
            if final_result_path.exists():
                try:
                    data = json.loads(final_result_path.read_text(encoding="utf-8"))
                    report_info["title"] = data.get("title", report_info["title"])
                    report_info["status"] = data.get("status", "COMPLETED")
                    report_info["duration"] = data.get("duration", 0)
                    report_info["num_speakers"] = data.get("num_speakers", 0)
                except Exception as e:
                    logger.warning(f"无法读取 final_result.json {meeting_id}: {e}")
                    
            reports.append(report_info)
            
    # 按时间倒序排列
    reports.sort(key=lambda x: x["created_at"], reverse=True)
    return reports

@router.get("/{meeting_id}/audio")
async def get_audio_stream(meeting_id: str, request: Request):
    """
    返回音频文件流，支持 HTTP Range。
    直接使用 Starlette/FastAPI 原生的 FileResponse，它天然支持 Range 解析和 206 Partial Content 返回。
    """
    audio_path = REPORTS_DIR / meeting_id / "audio.wav"
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")
        
    return FileResponse(
        str(audio_path),
        media_type="audio/wav",
        headers={"Accept-Ranges": "bytes"}
    )

@router.delete("/{meeting_id}")
async def delete_report(meeting_id: str):
    """彻底删除某次会议的所有产物"""
    target_dir = REPORTS_DIR / meeting_id
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="报告不存在")
        
    try:
        shutil.rmtree(target_dir)
        logger.info(f"成功删除报告文件夹: {meeting_id}")
        return {"status": "success", "message": f"成功删除 {meeting_id}"}
    except Exception as e:
        logger.error(f"删除文件夹失败 {meeting_id}: {e}")
        raise HTTPException(status_code=500, detail="删除失败，请检查文件占用")
