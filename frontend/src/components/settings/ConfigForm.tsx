"use client";

import { useState, useEffect } from "react";
import type { SystemConfig } from "@/types";

const Section = ({ title, children, bgColor = "bg-white" }: { title: string; children: React.ReactNode, bgColor?: string }) => (
  <div className={`brutal-box p-8 mb-8 ${bgColor}`}>
    <h2 className="text-2xl font-black uppercase mb-6 pb-4 border-b-4 border-black">
      {title}
    </h2>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">{children}</div>
  </div>
);

const InputRow = ({ label, value, onChange, placeholder, type = "text", hint }: { label: string; value: string; onChange: (val: string) => void; placeholder?: string; type?: string; hint?: string }) => (
  <div className="flex flex-col relative">
    <label className="text-sm font-bold uppercase mb-2 flex items-center group w-max">
      {label}
      {hint && (
        <span className="relative ml-2 w-5 h-5 inline-flex items-center justify-center bg-black text-white text-xs font-bold border-2 border-black group-hover:bg-[#ffc900] group-hover:text-black cursor-help transition-colors">
          ?
          <div className="absolute bottom-[calc(100%+12px)] -left-4 hidden group-hover:block w-64 p-4 bg-white text-black text-xs font-bold border-4 border-black z-50 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] normal-case whitespace-normal leading-relaxed text-left cursor-default">
            {hint}
            {/* 新粗野主义风格的对话框小角 (指向左下方 [?]) */}
            <div className="absolute left-6 -bottom-[10px] w-4 h-4 bg-white border-b-4 border-r-4 border-black transform rotate-45"></div>
          </div>
        </span>
      )}
    </label>
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="brutal-input bg-white"
    />
  </div>
);

export default function ConfigForm() {
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ llm?: boolean; feishu?: boolean; jira?: boolean } | null>(null);

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") {
      setConfig({ 
        llm_api_key: "sk-demo-mode-hidden", 
        llm_model: "gpt-4o-mini", 
        asr_engine: "auto", 
        whisper_device: "auto" 
      } as SystemConfig);
      setLoading(false);
      return;
    }
    fetch("/api/v1/config")
      .then((res) => res.json())
      .then((data) => {
        setConfig(data as SystemConfig);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load config", err);
        setLoading(false);
      });
  }, []);

  const handleChange = (key: keyof SystemConfig, value: string) => {
    if (config) {
      setConfig({ ...config, [key]: value });
    }
  };

  const handleSave = async () => {
    if (!config) return;
    if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") {
      alert("当前为静态演示模式，无法保存系统配置。");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch("/api/v1/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        alert("配置已成功保存！");
      } else {
        alert("保存失败");
      }
    } catch (err) {
      console.error(err);
      alert("保存出错");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") {
      setTestResult({ llm: true, feishu: true, jira: false });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch("/api/v1/config/status");
      const data = await res.json();
      setTestResult(data);
    } catch (err) {
      console.error("Test connection failed", err);
      alert("探测连接失败");
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64 font-black text-2xl uppercase">
        Loading...
      </div>
    );
  }

  if (!config) {
    return <div className="text-red-500 font-bold p-8">无法加载系统配置。</div>;
  }

  return (
    <div className="max-w-5xl mx-auto py-12 px-6">
      <div className="flex justify-between items-end mb-12 border-b-4 border-black pb-6">
        <div>
          <h1 className="text-5xl font-black">系统设置</h1>
          <p className="font-bold text-gray-700 mt-2">API 凭证与第三方集成</p>
        </div>
        <div className="flex space-x-4">
          <button onClick={handleTest} disabled={testing} className="brutal-btn brutal-btn-secondary">
            {testing ? "探测中..." : "探测连通性"}
          </button>
          <button onClick={handleSave} disabled={saving} className="brutal-btn brutal-btn-primary">
            {saving ? "保存中..." : "保存配置"}
          </button>
        </div>
      </div>

      {testResult && (
        <div className="brutal-box p-6 mb-12 bg-[#ffc900] flex items-center justify-between relative">
          <div className="flex space-x-8">
            <div className="flex items-center">
              <div className={`w-4 h-4 border-2 border-black mr-2 ${testResult.llm ? "bg-[#4ade80]" : "bg-[#f87171]"}`}></div>
              <span className="font-bold uppercase">大模型: {testResult.llm ? "OK" : "ERR"}</span>
            </div>
            <div className="flex items-center">
              <div className={`w-4 h-4 border-2 border-black mr-2 ${testResult.feishu ? "bg-[#4ade80]" : "bg-white"}`}></div>
              <span className="font-bold uppercase">飞书: {testResult.feishu ? "OK" : "SKIP"}</span>
            </div>
            <div className="flex items-center">
              <div className={`w-4 h-4 border-2 border-black mr-2 ${testResult.jira ? "bg-[#4ade80]" : "bg-white"}`}></div>
              <span className="font-bold uppercase">Jira: {testResult.jira ? "OK" : "SKIP"}</span>
            </div>
          </div>
          <button 
            onClick={() => setTestResult(null)}
            className="w-8 h-8 border-2 border-black bg-white flex items-center justify-center font-black hover:bg-[#f87171] hover:text-white transition-colors shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[1px_1px_0px_0px_rgba(0,0,0,1)]"
            title="关闭"
          >
            X
          </button>
        </div>
      )}

      <Section title="大语言模型 (LLM)" bgColor="bg-[#ff90e8]">
        <InputRow label="API 密钥 (LLM_API_KEY) [必填]" value={config.llm_api_key || ""} onChange={(v) => handleChange("llm_api_key", v)} placeholder="sk-..." type="password" hint="必须配置。例如：sk-proj-xxxxxxxx" />
        <InputRow label="服务商 (Provider) [选填]" value={config.llm_provider || ""} onChange={(v) => handleChange("llm_provider", v)} placeholder="openai, minimax, deepseek" />
        <InputRow label="模型名称 (LLM_MODEL) [选填]" value={config.llm_model || ""} onChange={(v) => handleChange("llm_model", v)} placeholder="gpt-4o-mini" hint="默认: gpt-4o-mini" />
        <InputRow label="请求地址 (Base URL) [选填]" value={config.llm_base_url || ""} onChange={(v) => handleChange("llm_base_url", v)} placeholder="https://api.openai.com/v1" hint="若为空，则默认请求官方 openai 接口" />
      </Section>

      <Section title="语音识别引擎 (ASR)" bgColor="bg-[#4ade80]">
        <div className="flex flex-col col-span-1 md:col-span-2">
          <label className="text-sm font-bold uppercase mb-2">引擎类型 (ASR_ENGINE)</label>
          <select
            value={config.asr_engine || "auto"}
            onChange={(e) => handleChange("asr_engine", e.target.value)}
            className="brutal-input bg-white cursor-pointer"
          >
            <option value="auto">Auto (根据语言自动侦测：中文用 FunASR，其他用 Whisper)</option>
            <option value="funasr">FunASR (阿里本地引擎 - 推荐中文场景)</option>
            <option value="sensevoice">SenseVoice (阿里多语言极速本地模型)</option>
            <option value="faster_whisper">Faster Whisper (经典本地化大模型)</option>
            <option value="openai">OpenAI Whisper API (云端第三方)</option>
            <option value="groq">Groq Whisper API (云端极速第三方)</option>
          </select>
        </div>

        {/* 本地引擎通用配置：Auto / FunASR / SenseVoice / Faster Whisper */}
        {["auto", "funasr", "sensevoice", "faster_whisper"].includes(config.asr_engine || "auto") && (
          <>
            <div className="flex flex-col">
              <label className="text-sm font-bold uppercase mb-2">本地计算设备 (WHISPER_DEVICE)</label>
              <select
                value={config.whisper_device || "auto"}
                onChange={(e) => handleChange("whisper_device", e.target.value)}
                className="brutal-input bg-white cursor-pointer"
              >
                <option value="auto">Auto (自动检测 CUDA/CPU)</option>
                <option value="cuda">CUDA (NVIDIA 显卡加速)</option>
                <option value="cpu">CPU (仅使用处理器计算)</option>
              </select>
            </div>
            <InputRow label="目标语言 (WHISPER_LANGUAGE) [选填]" value={config.whisper_language || ""} onChange={(v) => handleChange("whisper_language", v)} placeholder="zh, en, auto" />
          </>
        )}

        {/* 仅 Whisper 系列本地模型需要的配置 */}
        {["auto", "faster_whisper"].includes(config.asr_engine || "auto") && (
          <>
            <InputRow label="本地模型尺寸 (WHISPER_MODEL_SIZE) [必填]" value={config.whisper_model_size || ""} onChange={(v) => handleChange("whisper_model_size", v)} placeholder="tiny, base, small, medium, large-v3" hint="根据显存大小选择，默认: base" />
            <InputRow label="HuggingFace Token (HF_TOKEN) [选填]" value={config.hf_token || ""} onChange={(v) => handleChange("hf_token", v)} placeholder="hf_... " type="password" hint="仅在使用本地 Whisper 且需要 Pyannote 声纹分离时才需要填写。" />
          </>
        )}

        {/* 仅云端 API 模型需要的配置 */}
        {["openai", "groq"].includes(config.asr_engine || "auto") && (
          <>
            <InputRow label="云端 ASR API Key [必填]" value={config.asr_api_key || ""} onChange={(v) => handleChange("asr_api_key", v)} placeholder="sk-..." type="password" />
            <InputRow label="云端 ASR Base URL [选填]" value={config.asr_base_url || ""} onChange={(v) => handleChange("asr_base_url", v)} placeholder="自定义 API 转发地址" />
            <InputRow label="云端 ASR 模型名称 [选填]" value={config.asr_model || ""} onChange={(v) => handleChange("asr_model", v)} placeholder="whisper-1 / whisper-large-v3" hint="OpenAI为 whisper-1，Groq 通常为 whisper-large-v3" />
          </>
        )}
      </Section>

      <Section title="网络下载与抓取 (Downloads)" bgColor="bg-[#facc15]">
        <InputRow label="网络代理 (NOTEKING_PROXY) [选填]" value={config.noteking_proxy || ""} onChange={(v) => handleChange("noteking_proxy", v)} placeholder="socks5://127.0.0.1:7890" hint="国内环境访问 YouTube 等境外链接时必填（支持 HTTP / SOCKS5）。" />
        <InputRow label="Bilibili SESSDATA [选填]" value={config.bilibili_sessdata || ""} onChange={(v) => handleChange("bilibili_sessdata", v)} placeholder="your_sessdata_here" type="password" hint="B站会员 Cookie，用于下载 1080P/4K 超清视频。若为空则默认以游客身份下载 480P 画质。" />
      </Section>

      <Section title="飞书集成 (Feishu) [按需选填]" bgColor="bg-[#22d3ee]">
        <InputRow label="应用 ID (App ID) [选填]" value={config.feishu_app_id || ""} onChange={(v) => handleChange("feishu_app_id", v)} placeholder="cli_..." hint="若需飞书自动推送，则此项必填" />
        <InputRow label="应用密钥 (App Secret) [选填]" value={config.feishu_app_secret || ""} onChange={(v) => handleChange("feishu_app_secret", v)} placeholder="Secret Key" type="password" hint="若需飞书自动推送，则此项必填" />
        <InputRow label="接收群组/用户 ID [选填]" value={config.feishu_receive_id || ""} onChange={(v) => handleChange("feishu_receive_id", v)} placeholder="ou_..." hint="接收报告的目标会话 ID（群或个人）" />
        <InputRow label="群机器人 Webhook [选填]" value={config.feishu_webhook_url || ""} onChange={(v) => handleChange("feishu_webhook_url", v)} placeholder="https://open.feishu.cn/..." hint="仅通过纯 Webhook 推送卡片时填写" />
      </Section>

      <Section title="Jira 集成 [按需选填]" bgColor="bg-white">
        <InputRow label="Jira 服务地址 [选填]" value={config.jira_server || ""} onChange={(v) => handleChange("jira_server", v)} placeholder="https://domain.atlassian.net" hint="您的 Jira 域名，如需同步待办则必填" />
        <InputRow label="注册邮箱 [选填]" value={config.jira_email || ""} onChange={(v) => handleChange("jira_email", v)} placeholder="user@example.com" />
        <InputRow label="API Token [选填]" value={config.jira_api_token || ""} onChange={(v) => handleChange("jira_api_token", v)} placeholder="Jira Token" type="password" hint="在 Atlassian 账号安全中心生成" />
        <InputRow label="目标项目 Key [选填]" value={config.jira_project_key || ""} onChange={(v) => handleChange("jira_project_key", v)} placeholder="MEET" hint="待办事项归属的项目键值（默认: MEET）" />
      </Section>
    </div>
  );
}
