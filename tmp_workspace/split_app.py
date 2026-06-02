import os
app_file = 'services/application_service.py'
with open(app_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

def get_block(start_str, end_str=None):
    start_idx = -1
    for i, line in enumerate(lines):
        if start_str in line:
            start_idx = i
            break
    if start_idx == -1:
        return ''
    if end_str is None:
        return ''.join(lines[start_idx:])
    end_idx = -1
    for i in range(start_idx+1, len(lines)):
        if end_str in lines[i]:
            end_idx = i
            break
    if end_idx == -1:
        return ''.join(lines[start_idx:])
    return ''.join(lines[start_idx:end_idx+1])

# Extract functions
process_audio = get_block('async def process_audio_capture(', 'logger.info(f"[ApplicationService] 已自动清理 WebSocket 临时工作目录: {work_dir}")')
emit_agent = get_block('async def emit_agent_events(', '            "errors": final_state.get("errors", []),')
emit_agent_end = '        },\n    )\n'
emit_agent = emit_agent + emit_agent_end

run_offline = get_block('async def run_offline_pipeline(', '    return final_result')

online_imports = '''# -*- coding: utf-8 -*-
"""
在线实时音频流处理与 Agent 事件推送流水线
"""
import asyncio
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from services.media_engine import (
    detect_language,
    diarize,
    DiarizationResult,
    preprocess,
    transcribe,
)
from workflows.meeting_workflow import run_meeting_pipeline
from services.integrations import create_llm_client, FeishuClient, JiraClient
from utils import find_project_root, serialize_agent_outputs, create_fallback_diarization

ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

'''

offline_imports = '''# -*- coding: utf-8 -*-
"""
离线音视频文件/链接处理流水线
"""
import asyncio
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from loguru import logger

from services.media_engine import (
    align_frames_to_subtitles,
    detect_language,
    diarize,
    download_audio,
    download_video,
    extract_keyframes,
    parse_link,
    preprocess,
    transcribe,
)
from workflows.meeting_workflow import run_meeting_pipeline
from services.integrations import create_llm_client, FeishuClient, JiraClient
from schemas import JobConfig
from services.checkpoint_service import CheckpointService
from utils import find_project_root, serialize_agent_outputs, create_fallback_diarization, parse_transcript_file

_checkpoint = CheckpointService()
ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

'''

with open('services/pipeline/online_processor.py', 'w', encoding='utf-8') as f:
    f.write(online_imports + process_audio + "\n\n" + emit_agent)

with open('services/pipeline/offline_processor.py', 'w', encoding='utf-8') as f:
    f.write(offline_imports + run_offline + "\n")
