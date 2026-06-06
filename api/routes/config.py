# -*- coding: utf-8 -*-
from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
import os
import dotenv
from loguru import logger

router = APIRouter(prefix="/api/v1/config", tags=["Configuration"])

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

class ConfigPayload(BaseModel):
    # LLM Settings
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    
    # ASR Settings
    asr_engine: str | None = None
    whisper_device: str | None = None
    whisper_model_size: str | None = None
    whisper_language: str | None = None
    hf_token: str | None = None
    asr_api_key: str | None = None
    asr_base_url: str | None = None
    asr_model: str | None = None
    
    # Download Settings
    noteking_proxy: str | None = None
    bilibili_sessdata: str | None = None

    # Feishu Settings
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_receive_id: str | None = None
    feishu_webhook_url: str | None = None
    
    # Jira Settings
    jira_server: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    jira_project_key: str | None = None
    
    # System Settings
    port: str | None = None
    log_level: str | None = None

def _mask_secret(secret: str | None) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return secret[:8] + "..." + secret[-4:] if len(secret) > 12 else secret[:8] + "****"

@router.get("")
async def get_config():
    """读取并返回脱敏后的配置信息"""
    env_dict = dotenv.dotenv_values(ENV_PATH)
    
    return {
        "llm_provider": env_dict.get("LLM_PROVIDER", ""),
        "llm_api_key": _mask_secret(env_dict.get("LLM_API_KEY", "")),
        "llm_model": env_dict.get("LLM_MODEL", ""),
        "llm_base_url": env_dict.get("LLM_BASE_URL", ""),
        "asr_engine": env_dict.get("ASR_ENGINE", "auto"),
        "whisper_device": env_dict.get("WHISPER_DEVICE", "auto"),
        "whisper_model_size": env_dict.get("WHISPER_MODEL_SIZE", "base"),
        "whisper_language": env_dict.get("WHISPER_LANGUAGE", "zh"),
        "hf_token": _mask_secret(env_dict.get("HF_TOKEN", "")),
        "asr_api_key": _mask_secret(env_dict.get("ASR_API_KEY", "")),
        "asr_base_url": env_dict.get("ASR_BASE_URL", ""),
        "asr_model": env_dict.get("ASR_MODEL", "whisper-1"),
        "noteking_proxy": env_dict.get("NOTEKING_PROXY", ""),
        "bilibili_sessdata": _mask_secret(env_dict.get("BILIBILI_SESSDATA", "")),
        "feishu_app_id": env_dict.get("FEISHU_APP_ID", ""),
        "feishu_app_secret": _mask_secret(env_dict.get("FEISHU_APP_SECRET", "")),
        "feishu_receive_id": env_dict.get("FEISHU_RECEIVE_ID", ""),
        "feishu_webhook_url": env_dict.get("FEISHU_WEBHOOK_URL", ""),
        "jira_server": env_dict.get("JIRA_SERVER", ""),
        "jira_email": env_dict.get("JIRA_EMAIL", ""),
        "jira_api_token": _mask_secret(env_dict.get("JIRA_API_TOKEN", "")),
        "jira_project_key": env_dict.get("JIRA_PROJECT_KEY", ""),
        "port": env_dict.get("PORT", "8000"),
        "log_level": env_dict.get("LOG_LEVEL", "INFO"),
    }

@router.put("")
async def update_config(payload: ConfigPayload):
    """更新配置并写入 .env"""
    # 过滤掉包含 '*' 或 '...' 的伪脱敏值，防止覆盖真实密码
    updates = {
        "LLM_PROVIDER": payload.llm_provider,
        "LLM_API_KEY": payload.llm_api_key,
        "LLM_MODEL": payload.llm_model,
        "LLM_BASE_URL": payload.llm_base_url,
        "ASR_ENGINE": payload.asr_engine,
        "WHISPER_DEVICE": payload.whisper_device,
        "WHISPER_MODEL_SIZE": payload.whisper_model_size,
        "WHISPER_LANGUAGE": payload.whisper_language,
        "HF_TOKEN": payload.hf_token,
        "ASR_API_KEY": payload.asr_api_key,
        "ASR_BASE_URL": payload.asr_base_url,
        "ASR_MODEL": payload.asr_model,
        "NOTEKING_PROXY": payload.noteking_proxy,
        "BILIBILI_SESSDATA": payload.bilibili_sessdata,
        "FEISHU_APP_ID": payload.feishu_app_id,
        "FEISHU_APP_SECRET": payload.feishu_app_secret,
        "FEISHU_RECEIVE_ID": payload.feishu_receive_id,
        "FEISHU_WEBHOOK_URL": payload.feishu_webhook_url,
        "JIRA_SERVER": payload.jira_server,
        "JIRA_EMAIL": payload.jira_email,
        "JIRA_API_TOKEN": payload.jira_api_token,
        "JIRA_PROJECT_KEY": payload.jira_project_key,
        "PORT": payload.port,
        "LOG_LEVEL": payload.log_level,
    }
    
    for key, value in updates.items():
        if value is not None and "*" not in value and "..." not in value:
            dotenv.set_key(str(ENV_PATH), key, value, quote_mode="always")
            # 同步更新当前进程的环境变量，以免需要重启才能生效
            os.environ[key] = value
            
    logger.info("系统配置已更新")
    return {"status": "success", "message": "配置已成功保存"}

@router.get("/status")
async def check_status():
    """探测 LLM 及各个集成的可用性"""
    from services.integrations import create_llm_client, FeishuClient, JiraClient
    
    status = {
        "llm": False,
        "feishu": False,
        "jira": False
    }
    
    # 1. 测 LLM
    try:
        client = create_llm_client()
        # 发送简单的 ping 测试
        model_name = os.getenv("LLM_MODEL", "")
        if client and model_name:
            # UnifiedLLMClient 有自己的 chat 异步包装方法，而不是原生的 openai SDK
            response_text = await client.chat(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            if response_text is not None:
                status["llm"] = True
    except Exception as e:
        status["llm_error"] = str(e)
        logger.warning(f"LLM 探测失败: {e}")
        
    # 2. 测 Feishu
    try:
        feishu = FeishuClient()
        if feishu.is_enabled:
            # 获取 token 会触发真实的 API 调用测试凭证
            token = await feishu._get_tenant_token()
            if token:
                status["feishu"] = True
    except Exception as e:
        status["feishu_error"] = str(e)
        logger.warning(f"Feishu 探测失败: {e}")
        
    # 3. 测 Jira
    try:
        jira = JiraClient()
        if jira.is_enabled:
            # 获取自身信息验证 Basic Auth 是否有效
            user = jira._get_client().myself()
            if user:
                status["jira"] = True
    except Exception as e:
        status["jira_error"] = str(e)
        logger.warning(f"Jira 探测失败: {e}")
        
    return status
