# -*- coding: utf-8 -*-
"""
ASR Engine Pool（自动语音识别引擎池）
- 工厂模式组装，解耦全局 AppConfig 依赖
- 支持阿里 FunASR (Paraformer/SenseVoice) 本地高精度转录
- 支持 CPU/GPU (CUDA) 自动探测与硬件适配运行
- 内置 Groq / OpenAI 云端 Whisper API 作为高可用降级兜底方案
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from loguru import logger

from .subtitle import SubtitleResult, SubtitleSegment

class ASREngine(ABC):
    name: str = "base"

    @abstractmethod
    def transcribe(self, audio_path: Path, language: str = "zh") -> SubtitleResult:
        ...

    @classmethod
    def is_available(cls) -> bool:
        return True

class FunASREngine(ASREngine):
    name = "funasr"

    def __init__(self, model: str = "paraformer-zh"):
        self.model_name = model
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            from funasr import AutoModel
            import os
            from pathlib import Path

            # 工具函数：尝试转换模型 ID 为本地绝对路径
            def get_offline_path(alias_or_path: str) -> str:
                if Path(alias_or_path).exists(): return alias_or_path
                
                # FunASR 内置别名与真实 ModelScope 仓库名的映射
                alias_map = {
                    "fsmn-vad": "speech_fsmn_vad_zh-cn-16k-common-pytorch",
                    "ct-punc": "punc_ct-transformer_cn-en-common-vocab471067-large",
                    "cam++": "speech_campplus_sv_zh-cn_16k-common",
                    "paraformer-zh": "speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
                }
                
                ms_name = alias_map.get(alias_or_path, alias_or_path)
                check_id = ms_name if "/" in ms_name else f"iic/{ms_name}"
                
                # 检查默认缓存目录，兼容带 models 目录或不带 models 目录的结构
                cache_dir_with_models = Path.home() / ".cache" / "modelscope" / "hub" / "models" / check_id
                cache_dir_direct = Path.home() / ".cache" / "modelscope" / "hub" / check_id
                
                if cache_dir_with_models.exists():
                    return str(cache_dir_with_models)
                if cache_dir_direct.exists():
                    return str(cache_dir_direct)
                
                # 找不到缓存时，必须返回原始的别名让 FunASR 自己处理下载
                return alias_or_path

            self._pipeline = AutoModel(
                model=get_offline_path(self.model_name),
                vad_model=get_offline_path("fsmn-vad"),
                punc_model=get_offline_path("ct-punc"),
                spk_model=get_offline_path("cam++"),
                disable_update=True,
            )
        return self._pipeline

    def transcribe(self, audio_path: Path, language: str = "zh") -> SubtitleResult:
        pipeline = self._get_pipeline()
        result = pipeline.generate(
            input=str(audio_path),
            batch_size_s=300,
        )

        segments = []
        if result and len(result) > 0:
            item = result[0]
            text = item.get("text", "")
            timestamps = item.get("timestamp", [])
            sentence_info = item.get("sentence_info", [])

            if sentence_info:
                for sent in sentence_info:
                    seg_text = sent.get("text", "")
                    start_ms = sent.get("start", 0)
                    end_ms = sent.get("end", 0)
                    spk_id = sent.get("spk", 0)
                    segments.append(SubtitleSegment(
                        start=start_ms / 1000.0,
                        end=end_ms / 1000.0,
                        text=seg_text.strip(),
                        speaker=f"Speaker {spk_id + 1}" if isinstance(spk_id, int) else str(spk_id),
                    ))
            elif timestamps:
                for ts in timestamps:
                    if len(ts) >= 2:
                        start_ms = ts[0]
                        end_ms = ts[1]
                        segments.append(SubtitleSegment(
                            start=start_ms / 1000.0,
                            end=end_ms / 1000.0,
                            text="",
                        ))
                if text and not any(s.text for s in segments):
                    if segments:
                        segments[0] = SubtitleSegment(
                            start=segments[0].start,
                            end=segments[-1].end,
                            text=text.strip(),
                        )
                        segments = [segments[0]]
            elif text:
                segments.append(SubtitleSegment(start=0, end=0, text=text.strip()))

        return SubtitleResult(segments=segments, source="asr", language=language)

    @classmethod
    def is_available(cls) -> bool:
        try:
            import funasr
            return True
        except ImportError:
            return False

class SenseVoiceEngine(ASREngine):
    name = "sensevoice"

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            from funasr import AutoModel
            import os
            from pathlib import Path
            
            # 探测本地缓存路径，强制走离线模式阻断 .mv 联网更新 (兼容带 models 目录的结构)
            local_cache_path_models = Path.home() / ".cache" / "modelscope" / "hub" / "models" / "iic" / "SenseVoiceSmall"
            local_cache_path_direct = Path.home() / ".cache" / "modelscope" / "hub" / "iic" / "SenseVoiceSmall"
            
            if local_cache_path_models.exists():
                model_id_or_path = str(local_cache_path_models)
            elif local_cache_path_direct.exists():
                model_id_or_path = str(local_cache_path_direct)
            else:
                model_id_or_path = "iic/SenseVoiceSmall"
            
            self._model = AutoModel(model=model_id_or_path, disable_update=True)
        return self._model

    def transcribe(self, audio_path: Path, language: str = "zh") -> SubtitleResult:
        model = self._get_model()
        result = model.generate(
            input=str(audio_path),
            language="auto",
            use_itn=True,
        )

        segments = []
        if result and len(result) > 0:
            text = result[0].get("text", "")
            if text:
                segments.append(SubtitleSegment(start=0, end=0, text=text.strip()))

        return SubtitleResult(segments=segments, source="asr", language=language)

    @classmethod
    def is_available(cls) -> bool:
        try:
            import funasr
            return True
        except ImportError:
            return False

class FasterWhisperEngine(ASREngine):
    name = "faster_whisper"

    def __init__(self, model_size: str = "base", device: str = "auto"):
        self.model_size = model_size
        self.device = device
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type="auto"
            )
        return self._model

    def transcribe(self, audio_path: Path, language: str = "zh") -> SubtitleResult:
        model = self._get_model()
        segs, info = model.transcribe(
            str(audio_path), language=language, vad_filter=True
        )
        segments = []
        for seg in segs:
            segments.append(SubtitleSegment(
                start=seg.start, end=seg.end, text=seg.text.strip()
            ))
        return SubtitleResult(
            segments=segments, source="asr", language=info.language
        )

    @classmethod
    def is_available(cls) -> bool:
        try:
            import faster_whisper
            return True
        except ImportError:
            return False

class GroqWhisperEngine(ASREngine):
    name = "groq"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def transcribe(self, audio_path: Path, language: str = "zh") -> SubtitleResult:
        import httpx

        with open(audio_path, "rb") as f:
            resp = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (audio_path.name, f, "audio/wav")},
                data={
                    "model": "whisper-large-v3",
                    "response_format": "verbose_json",
                    "language": language,
                },
                timeout=300,
            )
        resp.raise_for_status()
        data = resp.json()
        segments = []
        for seg in data.get("segments", []):
            segments.append(SubtitleSegment(
                start=seg["start"], end=seg["end"], text=seg["text"].strip()
            ))
        if not segments and data.get("text"):
            segments.append(SubtitleSegment(start=0, end=0, text=data["text"]))
        return SubtitleResult(segments=segments, source="asr", language=language)

    @classmethod
    def is_available(cls) -> bool:
        return bool(os.getenv("GROQ_API_KEY"))

class OpenAIWhisperEngine(ASREngine):
    name = "openai_whisper"

    def __init__(self, api_key: str, base_url: str | None = None, model: str = "whisper-1"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def transcribe(self, audio_path: Path, language: str = "zh") -> SubtitleResult:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url) if self.base_url else OpenAI(api_key=self.api_key)
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model=self.model,
                file=f,
                response_format="verbose_json",
                language=language,
            )

        segments = []
        for seg in getattr(transcript, "segments", []) or []:
            segments.append(SubtitleSegment(
                start=seg["start"], end=seg["end"], text=seg["text"].strip()
            ))
        if not segments and transcript.text:
            segments.append(SubtitleSegment(start=0, end=0, text=transcript.text))
        return SubtitleResult(segments=segments, source="asr", language=language)

    @classmethod
    def is_available(cls) -> bool:
        return bool(os.getenv("ASR_API_KEY"))

def detect_language(audio_path: Path) -> str:
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="auto", compute_type="auto")
        _, info = model.transcribe(str(audio_path), language=None, vad_filter=True)
        detected = info.language
        prob = info.language_probability
        logger.info(f"检测到语言: {detected} (置信度: {prob:.2f})")
        if prob > 0.5:
            return detected
    except (ImportError, Exception) as e:
        logger.debug(f"语言检测失败: {e}")

    return "zh"

def is_chinese_dominant(lang: str) -> bool:
    return lang in ("zh", "yue", "wuu", "nan", "hak")

def _create_engine(language: str = "zh") -> ASREngine:
    pref = os.getenv("ASR_ENGINE", "auto")
    model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
    device = os.getenv("WHISPER_DEVICE", "auto")
    groq_key = os.getenv("GROQ_API_KEY", "")

    # 获取 ASR 专属 API Key
    asr_key = os.getenv("ASR_API_KEY")
    # 获取 ASR 专属 Base URL
    asr_base_url = os.getenv("ASR_BASE_URL")
    # 获取 ASR 专属模型名称
    asr_model = os.getenv("ASR_MODEL") or "whisper-1"

    if pref == "funasr" and FunASREngine.is_available():
        return FunASREngine()
    if pref == "sensevoice" and SenseVoiceEngine.is_available():
        return SenseVoiceEngine()
    if pref == "faster_whisper" and FasterWhisperEngine.is_available():
        return FasterWhisperEngine(model_size, device)
    if pref == "groq" and groq_key:
        return GroqWhisperEngine(groq_key)
    if pref == "openai" and asr_key:
        return OpenAIWhisperEngine(asr_key, base_url=asr_base_url, model=asr_model)

    if pref == "auto":
        if is_chinese_dominant(language) and FunASREngine.is_available():
            return FunASREngine()
        if FasterWhisperEngine.is_available():
            return FasterWhisperEngine(model_size, device)
        if SenseVoiceEngine.is_available():
            return SenseVoiceEngine()

    if groq_key:
        return GroqWhisperEngine(groq_key)
    if asr_key:
        return OpenAIWhisperEngine(asr_key, base_url=asr_base_url, model=asr_model)
    if FasterWhisperEngine.is_available():
        return FasterWhisperEngine(model_size, device)

    raise RuntimeError("No ASR engine available. Please configure local models or Cloud API keys.")

def transcribe(
    audio_path: Path,
    language: str | None = None,
) -> SubtitleResult:
    if language is None:
        language = detect_language(audio_path)

    engine = _create_engine(language)
    logger.info(f"使用语音识别引擎: {engine.name} (语言: {language})")
    return engine.transcribe(audio_path, language)
