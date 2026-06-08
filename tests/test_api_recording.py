# -*- coding: utf-8 -*-
"""
FastAPI 路由与 WebSocket 集成测试
- 验证上传接口、离线处理接口和 SSE 流式推送
- 利用 unittest.mock 拦截媒体引擎，验证离线处理接口和 SSE 流式推送
- 验证 WebSocket 实时音频帧处理与中间状态流式推送
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from interfaces.api.main import app
from services.media_engine import DiarizationResult, DiarizedSegment
from schemas import (
    MeetingGraphState,
    SummaryOutput,
    ActionOutput,
    ActionItem,
    InsightOutput,
    FollowUpOutput,
    FollowUpArtifacts,
)

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_reports_static_endpoint():
    from utils import get_reports_dir
    reports_dir = get_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "test-report.md"
    report_path.write_text("# test report\n", encoding="utf-8")

    try:
        response = client.get("/reports/test-report.md")
        assert response.status_code == 200
        assert response.text.strip() == "# test report"
    finally:
        report_path.unlink(missing_ok=True)

def test_upload_endpoint():
    file_content = b"fake audio data"
    file_obj = io.BytesIO(file_content)
    response = client.post(
        "/api/v1/recording/upload",
        files={"file": ("test.wav", file_obj, "audio/wav")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert data["filename"] == "test.wav"
    assert data["size"] == len(file_content)

@patch("api.routes.recording.run_offline_pipeline")
def test_process_endpoint(mock_run_offline_pipeline):
    mock_run_offline_pipeline.return_value = {
        "meeting_id": "test-mtg-123",
        "status": "COMPLETED",
        "summary": {"title": "测试会议摘要"},
        "actions": {"action_items": [{"assignee": "张三", "task": "完成测试"}]},
        "insights": {"overall_sentiment": "positive"},
        "followup": {"artifacts": {"markdown_path": "/reports/test-mtg-123.md"}},
    }

    with patch("api.routes.recording._UPLOAD_DIR") as mock_upload_dir:
        mock_upload_dir.glob.return_value = [Path("dummy.wav")]

        response = client.post(
            "/api/v1/recording/process",
            data={
                "file_id": "some-id",
                "denoise_level": 1,
                "extract_frames": False
            }
        )
        
    assert response.status_code == 200
    res_data = response.json()
    assert len(res_data["meeting_id"]) == 12
    assert res_data["status"] == "COMPLETED"
    assert res_data["summary"]["title"] == "测试会议摘要"
    assert len(res_data["actions"]["action_items"]) == 1
    assert res_data["actions"]["action_items"][0]["assignee"] == "张三"
    mock_run_offline_pipeline.assert_called_once()
    assert len(mock_run_offline_pipeline.call_args[1]["meeting_id"]) == 12
    assert "template" not in mock_run_offline_pipeline.call_args[1]

@patch("api.routes.recording.run_offline_pipeline")
def test_process_stream_endpoint(mock_run_offline_pipeline):
    async def mock_pipeline(**kwargs):
        progress_callback = kwargs["progress_callback"]
        await progress_callback("preprocess", {"message": "正在预处理"})
        await progress_callback("transcribe", {"message": "正在转写"})
        await progress_callback("diarize", {"message": "正在分割"})
        await progress_callback("agent_running", {"message": "正在分析"})
        return {
            "meeting_id": kwargs["meeting_id"],
            "status": "COMPLETED",
            "summary": {"title": "测试流式摘要"},
        }

    mock_run_offline_pipeline.side_effect = mock_pipeline

    with patch("api.routes.recording._UPLOAD_DIR") as mock_upload_dir:
        mock_upload_dir.glob.return_value = [Path("dummy.wav")]

        response = client.post(
            "/api/v1/recording/process/stream",
            data={
                "file_id": "some-id",
                "extract_frames": False
            }
        )
        
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
    # 验证 SSE 数据事件序列
    lines = response.text.strip().split("\n\n")
    events = [json.loads(line.replace("data: ", "").strip()) for line in lines if line.startswith("data:")]
    
    stages = [ev["stage"] for ev in events]
    assert "preprocess" in stages
    assert "transcribe" in stages
    assert "diarize" in stages
    assert "agent_running" in stages
    
    done_event = next(ev for ev in events if ev["stage"] == "done")
    assert len(done_event["meeting_id"]) == 12
    assert done_event["summary"]["title"] == "测试流式摘要"
    mock_run_offline_pipeline.assert_called_once()
    assert mock_run_offline_pipeline.call_args[1]["meeting_id"] == done_event["meeting_id"]
    assert "template" not in mock_run_offline_pipeline.call_args[1]

@patch("api.routes.websocket.run_meeting_pipeline")
def test_websocket_demo_mode(mock_run_pipeline):
    mock_run_pipeline.return_value = MeetingGraphState(
        meeting_id="ws-demo-id",
        status="COMPLETED",
        summary=SummaryOutput(title="WebSocket演示摘要"),
        actions=ActionOutput(meeting_id="ws-demo-id", action_items=[ActionItem(assignee="PM", task="跟进原型")]),
        insights=InsightOutput(meeting_id="ws-demo-id", overall_sentiment="neutral"),
        followup=FollowUpOutput(
            meeting_id="ws-demo-id",
            artifacts=FollowUpArtifacts(markdown_path="/reports/ws-demo-id.md")
        )
    )
    
    with client.websocket_connect("/ws/meeting/ws-demo-id") as websocket:
        # 1. 验证握手成功通知
        conn_msg = websocket.receive_json()
        assert conn_msg["type"] == "connected"
        
        # 2. 发送 demo 模式请求
        websocket.send_json({"type": "demo"})
        
        # 3. 验证处理状态推送
        proc_msg = websocket.receive_json()
        assert proc_msg["type"] == "processing"
        
        # 4. 验证 Mock 的说话人分割状态推送
        diar_msg = websocket.receive_json()
        assert diar_msg["type"] == "diarization"
        assert diar_msg["data"]["num_speakers"] == 4
        
        # 5. 验证各 Agent 流式反馈
        results = {}
        for _ in range(5):  # summary, actions, insights, followup, completed
            msg = websocket.receive_json()
            results[msg["type"]] = msg
            
        assert "summary" in results
        assert "actions" in results
        assert "insights" in results
        assert "followup" in results
        assert "completed" in results
        
        assert results["summary"]["data"]["title"] == "WebSocket演示摘要"
        assert results["actions"]["data"]["action_items"][0]["assignee"] == "PM"
        assert results["completed"]["data"]["status"] == "COMPLETED"


@patch("api.routes.websocket.process_audio_capture")
def test_websocket_stop_mode(mock_process_audio_capture):
    mock_process_audio_capture.return_value = (
        MeetingGraphState(
            meeting_id="ws-stop-id",
            status="COMPLETED",
            summary=SummaryOutput(title="实时摘要"),
            actions=ActionOutput(meeting_id="ws-stop-id"),
            insights=InsightOutput(meeting_id="ws-stop-id", overall_sentiment="neutral"),
            followup=FollowUpOutput(meeting_id="ws-stop-id"),
        ),
        DiarizationResult(
            segments=[DiarizedSegment(start=0.0, end=1.0, text="你好", speaker="Speaker 1")],
            num_speakers=1,
            speakers=["Speaker 1"],
            language="zh",
        ),
        {
            "segments": [{"start": 0.0, "end": 1.0, "text": "你好"}],
            "language": "zh",
            "source": "asr",
        },
    )

    with client.websocket_connect("/ws/meeting/ws-stop-id") as websocket:
        conn_msg = websocket.receive_json()
        assert conn_msg["type"] == "connected"

        websocket.send_bytes(b"fake-audio")
        recording_msg = websocket.receive_json()
        assert recording_msg["type"] == "recording"

        websocket.send_json({"type": "stop"})
        processing_msg = websocket.receive_json()
        assert processing_msg["type"] == "processing"

        transcript_msg = websocket.receive_json()
        assert transcript_msg["type"] == "transcript"
        assert transcript_msg["data"]["language"] == "zh"

        diarization_msg = websocket.receive_json()
        assert diarization_msg["type"] == "diarization"
        assert diarization_msg["data"]["num_speakers"] == 1

        result_types = [websocket.receive_json()["type"] for _ in range(5)]
        assert result_types == ["summary", "actions", "insights", "followup", "completed"]
    assert mock_process_audio_capture.call_args[1]["audio_bytes"] == b"fake-audio"
