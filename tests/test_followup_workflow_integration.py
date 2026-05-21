# -*- coding: utf-8 -*-
"""
Integration and unit tests for FollowUpAgent workflow, assets generation, and closed-loop integrations.
"""

from __future__ import annotations
import os
import shutil
import pytest
import tempfile
import httpx
import asyncio
from pathlib import Path
from unittest import mock
from datetime import datetime

from schemas import (
    MeetingGraphState,
    SummaryOutput,
    ActionOutput,
    InsightOutput,
    FollowUpOutput,
    TopicDetail,
    ActionItem,
    SpeakerStat,
)
from services.integrations.feishu_client import FeishuClient
from services.integrations.jira_client import JiraClient
from agents.followup_agent import FollowUpAgent
from services.media_engine import ExtractedFrame
from services import ReportComposer, ReportRenderer, MindMapService, ReportDelivery



# ----------------------------------------------------------------------
# 1. Feishu Client Tests
# ----------------------------------------------------------------------

def test_feishu_client_upload_and_send():
    """测试飞书客户端文件上传和发送 API"""
    async def run_test():
        client = FeishuClient(app_id="test_app", app_secret="test_secret")
        
        # 模拟 HTTP 响应
        async def mock_post(url, *args, **kwargs):
            class MockResponse:
                def __init__(self, json_data, status_code=200):
                    self.json_data = json_data
                    self.status_code = status_code
                def json(self):
                    return self.json_data
            
            if "tenant_access_token" in url:
                return MockResponse({"tenant_access_token": "token_123", "expire": 7200})
            elif "im/v1/files" in url:
                return MockResponse({"code": 0, "data": {"file_key": "file_key_999"}})
            elif "im/v1/messages" in url:
                return MockResponse({"code": 0, "msg": "success"})
            return MockResponse({"code": -1})

        # 使用临时文件测试上传
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.pdf"
            test_file.write_bytes(b"pdf dummy data")
            
            with mock.patch.object(client._client, "post", side_effect=mock_post):
                file_key = await client.upload_file(test_file, file_type="pdf")
                assert file_key == "file_key_999"
                
                success = await client.send_file(receive_id="chat_123", file_key=file_key)
                assert success is True

    asyncio.run(run_test())


# ----------------------------------------------------------------------
# 2. Jira Client Tests
# ----------------------------------------------------------------------

def test_jira_client_add_attachment():
    """测试 Jira 客户端附件上传 API"""
    client = JiraClient(server="http://jira.test", email="a@b.com", api_token="tok", project_key="MEET")
    assert client.is_enabled is True
    
    mock_jira_instance = mock.MagicMock()
    with mock.patch.object(client, "_get_client", return_value=mock_jira_instance):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.pdf"
            test_file.write_bytes(b"dummy")
            
            success = client.add_attachment(issue_key="MEET-101", file_path=test_file)
            assert success is True
            mock_jira_instance.add_attachment.assert_called_once()


# ----------------------------------------------------------------------
# 3. Follow-up Agent Tests
# ----------------------------------------------------------------------

def test_followup_agent_process_flow():
    """测试 FollowUpAgent 汇聚、动态排版、文档生成与分发的完整流程"""
    async def run_test():
        # 准备 Mock LLM
        mock_llm = mock.MagicMock()
        # 模拟 chat 异步方法返回已排版的 markdown
        async def mock_chat(messages, *args, **kwargs):
            # 验证消息中包含图像占位符排版命令
            assert any("IMAGE" in m["content"] for m in messages)
            return "## 动态融合排版报告\n\n讨论了技术架构。{IMAGE:1}\n*图 1：视频架构展示帧*"
        mock_llm.chat = mock_chat

        # 模拟 chat_sync 同步方法返回思维导图代码
        def mock_chat_sync(*args, **kwargs):
            return "```mermaid\nmindmap\n  root((技术重构会议))\n```"
        mock_llm.chat_sync = mock_chat_sync

        # 准备 Mock Feishu & Jira
        mock_feishu = mock.MagicMock()
        mock_feishu.is_enabled = True
        mock_feishu.receive_id = "group_chat_id"
        # mock 飞书异步方法 using AsyncMock
        mock_feishu.upload_file = mock.AsyncMock(side_effect=lambda file_path, file_type="pdf": f"mocked_key_{file_type}")
        mock_feishu.send_file = mock.AsyncMock(return_value=True)
        mock_feishu.send_meeting_summary = mock.AsyncMock(return_value=True)

        mock_jira = mock.MagicMock()
        mock_jira.is_enabled = True

        # 初始化 FollowUpAgent
        agent = FollowUpAgent(feishu_client=mock_feishu, jira_client=mock_jira, llm_client=mock_llm)

        # 构造输入 State
        summary = SummaryOutput(
            title="技术重构会议",
            participants=["张三", "李四"],
            topics=[TopicDetail(title="架构重构", discussion_points=["微服务拆分", "引入 API 网关"])]
        )
        actions = ActionOutput(
            action_items=[
                ActionItem(task="完成网关代码", assignee="张三", deadline="2026-06-01", jira_issue_key="MEET-202"),
                ActionItem(task="配置 CI/CD", assignee="李四", deadline="2026-06-05")
            ]
        )
        insights = InsightOutput(
            overall_sentiment="Positive",
            sentiment_score=0.85,
            efficiency_score=9.0,
            speaker_stats=[SpeakerStat(speaker="张三", speaking_duration=120.0, speaking_ratio=0.6, segment_count=5)]
        )
        
        # 构造临时测试用关键帧图片
        with tempfile.TemporaryDirectory() as tmpdir:
            frame_img = Path(tmpdir) / "frame_001.jpg"
            frame_img.write_bytes(b"image data")
            
            keyframes = [
                ExtractedFrame(
                    path=frame_img,
                    timestamp=45.2,
                    subtitle_text="这是架构设计的核心网关层"
                )
            ]

            state = {
                "meeting_id": "test_meeting_t6",
                "summary": summary,
                "actions": actions,
                "insights": insights,
                "keyframes": keyframes
            }

            # 运行 FollowUpAgent.process
            # 避开真实的 xelatex 与 chrome 打印
            with mock.patch("services.document_engine.pdf_engine.LaTeXNoteBuilder.compile_pdf", return_value=None):
                with mock.patch("services.document_engine.pdf_engine.HTMLNoteBuilder.html_to_pdf", return_value=True) as mock_html_to_pdf:
                    # 预先创建空的 PDF 文件，模拟编译或浏览器成功输出的情形
                    reports_dir = Path(__file__).resolve().parents[1] / "reports"
                    reports_dir.mkdir(parents=True, exist_ok=True)
                    pdf_target = reports_dir / "test_meeting_t6.pdf"
                    pdf_target.write_bytes(b"x" * 6000)
                    
                    result = await agent.process(state)
                    
                    assert result["status"] == "COMPLETED"
                    followup_data = result["followup"]
                    assert followup_data.meeting_id == "test_meeting_t6"
                    
                    # 检查 Markdown 报告是否在 reports 中写入
                    md_report = reports_dir / "test_meeting_t6.md"
                    assert md_report.exists()
                    report_content = md_report.read_text(encoding="utf-8")
                    assert "动态融合排版报告" in report_content

                    # 检查思维导图是否生成
                    mm_report = reports_dir / "test_meeting_t6_mindmap.md"
                    assert mm_report.exists()

                    # 检查最新的解耦结构化状态字段
                    assert followup_data.artifacts.markdown_path == str(md_report)
                    assert followup_data.artifacts.pdf_path == str(pdf_target)
                    assert followup_data.artifacts.mindmap_path == str(mm_report)
                    
                    # 检查分发结果
                    assert len(followup_data.delivery_results) == 2
                    feishu_res = next(r for r in followup_data.delivery_results if r.channel == "feishu")
                    assert feishu_res.success is True
                    jira_res = next(r for r in followup_data.delivery_results if r.channel == "jira")
                    assert jira_res.success is True

                    # 验证飞书和 Jira 的上传方法被成功调用
                    mock_feishu.upload_file.assert_called()
                    mock_feishu.send_file.assert_called()
                    mock_jira.add_attachment.assert_any_call("MEET-202", pdf_target)
                    mock_jira.add_attachment.assert_any_call("MEET-202", mm_report)
                    
                    # 清理临时生成的文件
                    for f in (md_report, pdf_target, mm_report, reports_dir / "test_meeting_t6.html"):
                        if f.exists():
                            f.unlink()

    asyncio.run(run_test())


def test_reporting_and_delivery_services_individually():
    """单元测试：独立验证 Composer、Renderer、MindMap 和 Delivery 服务"""
    async def run_test():
        # Mocks
        mock_llm = mock.MagicMock()
        async def mock_chat(messages, *args, **kwargs):
            return "## 独立服务测试报告\n\n内容已融合。{IMAGE:1}"
        mock_llm.chat = mock_chat

        def mock_chat_sync(*args, **kwargs):
            return "```mermaid\nmindmap\n  root((独立测试脑图))\n```"
        mock_llm.chat_sync = mock_chat_sync

        mock_feishu = mock.MagicMock()
        mock_feishu.is_enabled = True
        mock_feishu.receive_id = "chat_group"
        mock_feishu.send_meeting_summary = mock.AsyncMock(return_value=True)
        mock_feishu.upload_file = mock.AsyncMock(return_value="mock_key")
        mock_feishu.send_file = mock.AsyncMock(return_value=True)

        mock_jira = mock.MagicMock()
        mock_jira.is_enabled = True

        summary = SummaryOutput(title="单元测试会议", participants=["测试人"])
        actions = ActionOutput(action_items=[ActionItem(task="测试任务", assignee="测试人", jira_issue_key="TEST-1")])
        insights = InsightOutput(overall_sentiment="Positive", sentiment_score=0.9, efficiency_score=10.0)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            frame_img = temp_path / "frame.jpg"
            frame_img.write_bytes(b"img")
            keyframes = [ExtractedFrame(path=frame_img, timestamp=1.5, subtitle_text="关键幻灯片")]

            # 1. 测试 ReportComposer
            composer = ReportComposer(llm_client=mock_llm)
            report_md, kf_objects = await composer.compose_report(
                meeting_id="unit_test_mtg",
                summary=summary,
                actions=actions,
                insights=insights,
                keyframes=keyframes
            )
            assert "独立服务测试报告" in report_md
            assert len(kf_objects) == 1
            assert kf_objects[0].subtitle_text == "关键幻灯片"

            # 2. 测试 ReportRenderer
            renderer = ReportRenderer(reports_dir=temp_path)
            with mock.patch("services.document_engine.pdf_engine.LaTeXNoteBuilder.compile_pdf", return_value=None):
                with mock.patch("services.document_engine.pdf_engine.HTMLNoteBuilder.html_to_pdf", return_value=True):
                    # 预先创建空 PDF 绕过真实编译
                    pdf_dummy = temp_path / "unit_test_mtg.pdf"
                    pdf_dummy.write_bytes(b"pdfdata" * 1000)
                    
                    md_path, pdf_path, html_path, pdf_generated = await renderer.render_report(
                        meeting_id="unit_test_mtg",
                        final_report_md=report_md,
                        kf_objects=kf_objects
                    )
                    assert md_path.exists()
                    assert pdf_path.exists()
                    assert pdf_generated is True

            # 3. 测试 MindMapService
            mindmap_service = MindMapService(llm_client=mock_llm, reports_dir=temp_path)
            mm_path, mm_generated = await mindmap_service.generate_and_save_mindmap(
                meeting_id="unit_test_mtg",
                final_report_md=report_md
            )
            assert mm_path.exists()
            assert mm_generated is True
            assert "独立测试脑图" in mm_path.read_text(encoding="utf-8")

            # 4. 测试 ReportDelivery
            delivery = ReportDelivery(feishu_client=mock_feishu, jira_client=mock_jira)
            
            delivery_results = await delivery.deliver_report(
                meeting_id="unit_test_mtg",
                summary=summary,
                actions=actions,
                insights=insights,
                pdf_path=pdf_path,
                pdf_generated=pdf_generated,
                mindmap_path=mm_path,
                mindmap_generated=mm_generated,
            )
            
            assert len(delivery_results) == 2
            feishu_res = next(r for r in delivery_results if r.channel == "feishu")
            assert feishu_res.success is True
            assert "mock_key" in feishu_res.artifacts
            
            jira_res = next(r for r in delivery_results if r.channel == "jira")
            assert jira_res.success is True
            assert "TEST-1:unit_test_mtg.pdf" in jira_res.artifacts

    asyncio.run(run_test())


def test_report_delivery_success_calculations():
    """测试 ReportDelivery 的 success 是否真正基于上传/发送/挂载结果计算"""
    async def run_test():
        summary = SummaryOutput(title="测试会议", participants=["测试人"])
        actions = ActionOutput(action_items=[ActionItem(task="测试任务", assignee="测试人", jira_issue_key="TEST-1")])
        insights = InsightOutput(overall_sentiment="Positive", sentiment_score=0.9, efficiency_score=10.0)
        
        pdf_path = Path("dummy.pdf")
        mm_path = Path("dummy_mindmap.md")

        # Case 1: 飞书文本发送失败 -> 飞书 channel success 应为 False
        mock_feishu = mock.MagicMock()
        mock_feishu.is_enabled = True
        mock_feishu.receive_id = "chat_group"
        mock_feishu.send_meeting_summary = mock.AsyncMock(return_value=False)
        
        delivery = ReportDelivery(feishu_client=mock_feishu, jira_client=None)
        results = await delivery.deliver_report(
            meeting_id="test", summary=summary, actions=actions, insights=insights,
            pdf_path=pdf_path, pdf_generated=True, mindmap_path=mm_path, mindmap_generated=True,
        )
        assert results[0].success is False

        # Case 2: 飞书文本成功，但 PDF 上传失败 -> 飞书 channel success 应为 False
        mock_feishu = mock.MagicMock()
        mock_feishu.is_enabled = True
        mock_feishu.receive_id = "chat_group"
        mock_feishu.send_meeting_summary = mock.AsyncMock(return_value=True)
        mock_feishu.upload_file = mock.AsyncMock(side_effect=lambda path, file_type: "" if file_type == "pdf" else "mm_key")
        mock_feishu.send_file = mock.AsyncMock(return_value=True)
        
        delivery = ReportDelivery(feishu_client=mock_feishu, jira_client=None)
        results = await delivery.deliver_report(
            meeting_id="test", summary=summary, actions=actions, insights=insights,
            pdf_path=pdf_path, pdf_generated=True, mindmap_path=mm_path, mindmap_generated=True,
        )
        assert results[0].success is False

        # Case 3: 飞书文本成功，PDF 上传成功，但 PDF 发送失败 -> 飞书 channel success 应为 False
        mock_feishu = mock.MagicMock()
        mock_feishu.is_enabled = True
        mock_feishu.receive_id = "chat_group"
        mock_feishu.send_meeting_summary = mock.AsyncMock(return_value=True)
        mock_feishu.upload_file = mock.AsyncMock(return_value="key_123")
        send_file_mock = mock.AsyncMock()
        send_file_mock.side_effect = [False, True]
        mock_feishu.send_file = send_file_mock
        
        delivery = ReportDelivery(feishu_client=mock_feishu, jira_client=None)
        results = await delivery.deliver_report(
            meeting_id="test", summary=summary, actions=actions, insights=insights,
            pdf_path=pdf_path, pdf_generated=True, mindmap_path=mm_path, mindmap_generated=True,
        )
        assert results[0].success is False

        # Case 4: 飞书全部成功 -> 飞书 channel success 应为 True
        mock_feishu = mock.MagicMock()
        mock_feishu.is_enabled = True
        mock_feishu.receive_id = "chat_group"
        mock_feishu.send_meeting_summary = mock.AsyncMock(return_value=True)
        mock_feishu.upload_file = mock.AsyncMock(return_value="key_123")
        mock_feishu.send_file = mock.AsyncMock(return_value=True)
        
        delivery = ReportDelivery(feishu_client=mock_feishu, jira_client=None)
        results = await delivery.deliver_report(
            meeting_id="test", summary=summary, actions=actions, insights=insights,
            pdf_path=pdf_path, pdf_generated=True, mindmap_path=mm_path, mindmap_generated=True,
        )
        assert results[0].success is True
        assert len(results[0].artifacts) == 2

        # Case 5: Jira 挂载附件失败 -> Jira channel success 应为 False
        mock_jira = mock.MagicMock()
        mock_jira.is_enabled = True
        mock_jira.add_attachment = mock.MagicMock(return_value=False)
        
        delivery = ReportDelivery(feishu_client=None, jira_client=mock_jira)
        results = await delivery.deliver_report(
            meeting_id="test", summary=summary, actions=actions, insights=insights,
            pdf_path=pdf_path, pdf_generated=True, mindmap_path=mm_path, mindmap_generated=True,
        )
        assert results[0].success is False

        # Case 6: Jira 挂载附件成功 -> Jira channel success 应为 True
        mock_jira = mock.MagicMock()
        mock_jira.is_enabled = True
        mock_jira.add_attachment = mock.MagicMock(return_value=True)
        
        delivery = ReportDelivery(feishu_client=None, jira_client=mock_jira)
        results = await delivery.deliver_report(
            meeting_id="test", summary=summary, actions=actions, insights=insights,
            pdf_path=pdf_path, pdf_generated=True, mindmap_path=mm_path, mindmap_generated=True,
        )
        assert results[0].success is True
        assert len(results[0].artifacts) == 2

    asyncio.run(run_test())


