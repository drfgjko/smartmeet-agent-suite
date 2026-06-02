# -*- coding: utf-8 -*-
"""
发言人智能推断 (Speaker Inference Agent)
- 读取带有匿名发言人标记（如 Speaker 1, Speaker 2）的转录文本
- 根据上下文（打招呼、自我介绍、提问、相互称呼）推断发言人的真实姓名
- 全局替换转录文本与结构化声纹数据中的发言人名字
- 优雅降级：如果大模型推断失败或解析异常，则保留原始标记继续后续流程
"""

from __future__ import annotations

import json
from typing import Any
from loguru import logger
from pydantic import BaseModel, Field

from schemas import MeetingGraphState, SpeakerMapping

class SpeakerInferenceAgent:
    def __init__(self, llm_client: Any):
        self.llm_client = llm_client
        self.system_prompt = (
            "你是一个聪明的对话分析助手。\n"
            "你的任务是阅读一段包含多个匿名发言人（如 Speaker 1, Speaker 2）的会议转录文本，"
            "并根据对话中的上下文信息（例如互相打招呼、自我介绍、提问时的称呼等）推断出每个匿名发言人的真实姓名或身份。\n\n"
            "【规则】：\n"
            "1. 请仔细寻找上下文线索，比如“张总，您怎么看？”通常意味着被提问的人是张总。\n"
            "2. 如果有人的名字在整段对话中从未出现或无法推断，请保持他们原本的标签（如 'Speaker 1'）。\n"
            "3. 你的输出必须是一个合法的 JSON 对象，格式为 `{\"mappings\": [{\"original_label\": \"Speaker 1\", \"inferred_name\": \"张三\"}]}`。\n"
            "4. 不要输出任何多余的解释，只输出 JSON。"
        )

    async def process(self, state: MeetingGraphState) -> dict:
        """LangGraph 节点处理函数，直接返回需要合并到状态的字典"""
        logger.info(f"[{state.meeting_id}] Agent - SpeakerInference: 开始分析发言人身份...")

        transcript_text = state.transcript_text
        transcript = state.transcript

        # 如果没有有效的转录文本，直接跳过
        if not transcript_text or not transcript or not transcript.segments:
            logger.info("未发现有效的转录文本，跳过发言人推断。")
            return {}

        prompt = f"以下是转录文本，请推断并发言人的真实姓名：\n\n{transcript_text}"
        
        try:
            # 强制使用 chat_json 模式以确保返回 JSON
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
            data = await self.llm_client.chat_json(
                messages=messages
            )
            
            mapping_dict = {}
            try:
                speaker_mapping = SpeakerMapping.model_validate(data)
                for item in speaker_mapping.mappings:
                    mapping_dict[item.original_label] = item.inferred_name
            except Exception as e:
                logger.warning(f"[{state.meeting_id}] Agent - SpeakerInference: JSON 解析失败 ({e})，响应内容: {response}")
                mapping_dict = {}

            # 过滤掉无意义的自映射 (比如 'Speaker 1': 'Speaker 1')
            effective_mappings = {k: v for k, v in mapping_dict.items() if k and v and k != v}

            if not effective_mappings:
                logger.warning(f"[{state.meeting_id}] Agent - SpeakerInference: 未推断出任何有效的真实姓名，保留原始匿名标记。")
                return {}

            logger.info(f"[{state.meeting_id}] 推断得到的映射关系: {effective_mappings}")

            # 执行全局替换
            # 1. 替换 DiarizationResult.segments 中的 speaker
            new_segments = []
            for seg in transcript.segments:
                old_spk = seg.speaker or ""
                new_spk = effective_mappings.get(old_spk, old_spk)
                
                # 创建新的 seg (如果是 pydantic model 或者是 dataclass，这里需要注意。DiarizedSegment 是 dataclass)
                # 直接修改原对象的属性，或者创建新对象
                new_segments.append(seg)
                seg.speaker = new_spk

            # 更新 transcript.speakers 列表
            if transcript.speakers:
                new_speakers = []
                for s in transcript.speakers:
                    new_speakers.append(effective_mappings.get(s, s))
                transcript.speakers = list(set(new_speakers))

            # 2. 重新生成 transcript_text
            # 直接调用 property 的重新计算逻辑，但这要求我们提供一个新的方法，或者直接在这里重新生成
            lines = []
            current_speaker = None
            for seg in transcript.segments:
                if seg.speaker != current_speaker:
                    current_speaker = seg.speaker
                    lines.append(f"\n**{current_speaker or 'Unknown'}** ({seg.start_ts}):")
                lines.append(f"  {seg.text}")
            
            new_transcript_text = "\n".join(lines)

            logger.info(f"[{state.meeting_id}] Agent - SpeakerInference: 成功替换发言人标记并更新文本。")
            
            return {
                "transcript": transcript,
                "transcript_text": new_transcript_text
            }

        except Exception as e:
            # 优雅降级：如果调用大模型失败等，记录日志并跳过
            logger.warning(f"[{state.meeting_id}] Agent - SpeakerInference: 发生异常 ({e})，优雅降级，保留原始标记继续。")
            return {}
