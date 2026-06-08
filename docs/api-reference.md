# SmartMeet API 参考文档

## 一、基础信息

- **基础 URL**: `http://localhost:8000`
- **API 版本**: `1.0.0`
- **交互式文档**: Swagger UI 位于 `/docs`，ReDoc 位于 `/redoc`

---

## 二、系统接口

### 2.1 服务信息

```http
GET /
```

**响应示例**：

```json
{
  "name": "SmartMeet API",
  "version": "1.0.0",
  "docs": "/docs",
  "websocket": "ws://localhost:8000/ws/meeting/{meeting_id}"
}
```

### 2.2 健康检查

```http
GET /health
```

**响应示例**：

```json
{
  "status": "ok"
}
```

---

## 三、音视频处理接口

### 3.1 上传文件

```http
POST /api/v1/recording/upload
```

上传音视频文件到服务端临时目录，返回 `file_id` 用于后续处理。

**请求格式**：`multipart/form-data`

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 音视频文件（支持 MP4/MP3/WAV/M4A/WebM 等格式） |

**请求示例**：

```bash
curl -X POST http://localhost:8000/api/v1/recording/upload \
  -F "file=@meeting.mp4"
```

**响应示例**：

```json
{
  "file_id": "a1b2c3d4e5f6",
  "filename": "meeting.mp4",
  "size": 52428800,
  "path": "/tmp/smartmeet_uploads/a1b2c3d4e5f6.mp4"
}
```

---

### 3.2 离线处理（非流式）

```http
POST /api/v1/recording/process
```

提交音视频文件进行完整流水线处理，等待全部完成返回 JSON 结果。

**请求格式**：`application/x-www-form-urlencoded`

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `file_id` | string | 否 | - | 上传文件 ID（与 file_path/url 三选一） |
| `file_path` | string | 否 | - | 服务器本地文件路径（与 file_id/url 三选一） |
| `url` | string | 否 | - | 在线视频链接（与 file_id/file_path 三选一） |
| `context` | string | 否 | - | 补充上下文描述，帮助 AI 理解内容 |
| `num_speakers` | int | 否 | - | 预设发言人数，不传则自动检测 |
| `denoise_level` | int | 否 | 1 | 降噪强度（0=无，1=轻度，2=中度，3=重度） |
| `extract_frames` | bool | 否 | true | 是否提取视频关键帧 |

**请求示例**：

```bash
# 通过 file_id 处理上传的文件
curl -X POST http://localhost:8000/api/v1/recording/process \
  -d "file_id=a1b2c3d4e5f6" \
  -d "context=Q3预算评审会议" \
  -d "num_speakers=4" \
  -d "denoise_level=1"

# 通过在线链接处理
curl -X POST http://localhost:8000/api/v1/recording/process \
  -d "url=https://www.youtube.com/watch?v=xxxxx"

# 通过本地路径处理
curl -X POST http://localhost:8000/api/v1/recording/process \
  -d "file_path=/data/recordings/meeting.wav"
```

**响应示例**：

```json
{
  "meeting_id": "a1b2c3d4e5f6",
  "title": "Q3预算评审会议",
  "status": "COMPLETED",
  "duration": 3600.5,
  "num_speakers": 4,
  "speakers": ["张总", "李明", "王芳", "赵伟"],
  "transcript": "原始转录全文...",
  "diarized_transcript": "[张总] 好的，我们开始...\n[李明] 截至目前...",
  "content": "# Q3预算评审会议\n\n## 议题\n\n### 1. Q2预算执行情况...\n\n## 行动项\n\n- **李明**: 整理Q3详细预算方案...\n\n## 会议洞察\n\n- 整体氛围：积极...",
  "output_files": {
    "markdown": "/path/to/report/a1b2c3d4e5f6.md",
    "pdf": "/path/to/report/a1b2c3d4e5f6.pdf",
    "html": "/path/to/report/a1b2c3d4e5f6.html",
    "mindmap": "/path/to/report/a1b2c3d4e5f6.mm.md"
  },
  "summary": {
    "title": "Q3预算评审会议",
    "date": "2025-03-15",
    "participants": ["张总", "李明", "王芳", "赵伟"],
    "topics": [
      {
        "title": "Q2预算执行情况回顾",
        "discussion_points": ["Q2预算执行率87%", "研发投入占比42%"],
        "participants": ["张总", "李明"],
        "conclusion": "Q2执行情况良好，Q3需继续优化"
      }
    ],
    "decisions": ["Q3预算上调15%"],
    "next_steps": ["李明整理Q3预算方案"]
  },
  "actions": {
    "meeting_id": "a1b2c3d4e5f6",
    "action_items": [
      {
        "assignee": "李明",
        "task": "整理Q3详细预算方案",
        "deadline": "2025-03-22",
        "priority": "high",
        "context": "Q3预算上调15%"
      }
    ],
    "sync_status": {
      "jira": "synced",
      "feishu": "synced"
    }
  },
  "insights": {
    "meeting_id": "a1b2c3d4e5f6",
    "overall_sentiment": "positive",
    "sentiment_score": 0.85,
    "speaker_stats": [
      {"speaker": "张总", "speaking_duration": 320.5, "speaking_ratio": 0.35, "word_count": 1200, "segment_count": 15}
    ],
    "efficiency_score": 8.5,
    "keywords": ["预算", "Q3", "研发", "招聘"],
    "highlights": ["明确了Q3预算方向"],
    "suggestions": ["下次会议提前发放预算数据"]
  },
  "followup": {
    "meeting_id": "a1b2c3d4e5f6",
    "artifacts": {
      "markdown_path": "/path/to/report.md",
      "pdf_path": "/path/to/report.pdf",
      "html_path": "/path/to/report.html",
      "mindmap_path": "/path/to/report.mm.md"
    },
    "delivery_results": [
      {
        "channel": "feishu",
        "success": true,
        "targets": ["群聊: Q3预算群"],
        "artifacts": ["报告PDF", "思维导图"],
        "error": null
      }
    ]
  },
  "keyframes": [
    {
      "path": "/path/to/keyframes/frame_001.jpg",
      "timestamp": 120.5,
      "timestamp_str": "00:02:00.500",
      "subtitle_text": "好的，我们开始今天的Q3预算评审会议"
    }
  ],
  "errors": []
}
```

---

### 3.3 离线处理（SSE 流式）

```http
POST /api/v1/recording/process/stream
```

与 `/process` 接口参数完全一致，但通过 Server-Sent Events (SSE) 实时推送各处理阶段的进度。

**请求参数**：同 `/process` 接口

**响应格式**：SSE `text/event-stream`

**事件流示例**：

```text
data: {"stage": "started", "message": "正在解析并下载视频链接..."}

data: {"stage": "preprocess", "message": "正在进行媒体预处理（提取音轨、降噪）..."}

data: {"stage": "transcribe", "message": "正在进行语音识别转录..."}

data: {"stage": "diarize", "message": "正在进行说话人声纹识别与对齐..."}

data: {"stage": "keyframes", "message": "正在提取关键帧（仅视频支持）..."}

data: {"stage": "agent_running", "message": "AI 会议协同助理正在并行分析..."}

data: {"stage": "done", "meeting_id": "a1b2c3d4e5f6", "title": "Q3预算评审会议", "content": "...", ...}
```

---

### 3.4 离线处理（纯异步后台任务）

```http
POST /api/v1/recording/process/async
```

一键离线处理接口 (纯异步流)，提交任务后立即返回 Task ID，由后台队列异步执行。适合耗时极长的任务。

**请求参数**：同 `/process` 接口

**响应示例**：

```json
{
  "task_id": "d2c3b4a5-1234-...",
  "status": "pending",
  "message": "Task submitted successfully. Please poll /api/v1/tasks/{task_id} for status."
}
```

---

### 3.5 异步任务轮询查询

```http
GET /api/v1/tasks/{task_id}
```

轮询接口：获取由 `/process/async` 提交的异步任务的当前执行状态和最终产物。

**响应示例**：

```json
{
  "task_id": "d2c3b4a5-1234-...",
  "meeting_id": "a1b2c3d4e5f6",
  "status": "completed",
  "result": { ...最终的完整会议分析结果 JSON... },
  "error": null,
  "created_at": "2025-03-15T10:00:00Z",
  "updated_at": "2025-03-15T10:05:00Z"
}
```

---

### 3.6 原子化分析接口

```http
POST /api/v1/analyze
```

纯 JSON 分析接口 — 毫秒级返回结构化小卡片。只运行 LangGraph 分析 Agent，**不涉及**音视频处理、报告渲染和外部推送。

**请求格式**：`application/json`

**请求示例**：

```json
{
  "transcript_text": "**张总** (00:00:10):\n大家好，我们开始今天的会议...",
  "meeting_id": "a1b2c3d4e5f6",
  "job_config": {}
}
```

**响应示例**：返回精简的分析卡片，详见 `/process` 接口响应中的 `summary`, `actions`, `insights` 字段。

---

### 3.7 原子化渲染接口

```http
POST /api/v1/render
```

渲染接口 — 接受分析 Agent 输出的完整 JSON，独立生成 Markdown/PDF/HTML/思维导图报告（不包含外部任务同步与分发）。

**请求格式**：`application/json`

**请求示例**：

```json
{
  "meeting_id": "a1b2c3d4e5f6",
  "summary": { ... },
  "actions": { ... },
  "insights": { ... },
  "job_config": {
    "enable_report_render": true,
    "enable_mindmap": true
  }
}
```

**响应示例**：返回生成的资产路径，详见 `/process` 接口响应中的 `followup.artifacts` 字段。

---

### 3.8 纯交付接口 (Deliver)

```http
POST /api/v1/deliver
```

纯交付接口 — 接受分析 Agent 输出的完整 JSON，独立执行完整的交付流水线（包含排版渲染、思维导图生成、任务同步 Jira 以及多渠道分发飞书）。

**请求格式**：`application/json`

**请求示例**：

```json
{
  "meeting_id": "a1b2c3d4e5f6",
  "summary": { ... },
  "actions": { ... },
  "insights": { ... },
  "job_config": {
    "enable_report_render": true,
    "enable_mindmap": true,
    "enable_delivery": true,
    "feishu": {
      "enabled": true,
      "push_card": true,
      "push_pdf": true,
      "push_mindmap": true
    }
  },
  "sync_tasks": true
}
```

**响应示例**：返回生成的资产路径及同步、分发结果，详见 `/process` 接口响应中的 `followup` 和 `actions` 字段。

---

## 四、配置与管理接口

### 4.1 获取配置

```http
GET /api/v1/config
```

读取并返回系统脱敏后的配置信息（如 LLM 设置、ASR 设置、外部集成参数等）。

### 4.2 更新配置

```http
PUT /api/v1/config
```

更新系统配置并持久化保存。

**请求格式**：`application/json`

**请求示例**：

```json
{
  "llm_model": "gpt-4o-mini",
  "log_level": "DEBUG"
}
```

### 4.3 检测集成服务状态

```http
GET /api/v1/config/status
```

探测 LLM、飞书、Jira 等外部集成服务的当前可用性状态。

### 4.4 获取报告列表

```http
GET /api/v1/reports
```

获取系统中已处理的历史会议报告列表。

### 4.5 获取音频文件流

```http
GET /api/v1/reports/{meeting_id}/audio
```

获取某次会议的原始音频文件流，支持 HTTP Range。

### 4.6 删除报告

```http
DELETE /api/v1/reports/{meeting_id}
```

彻底删除指定会议的所有报告及产物文件。

---

## 五、WebSocket 实时接口

### 4.1 连接

```http
WebSocket ws://localhost:8000/ws/meeting/{meeting_id}
```

| 路径参数 | 类型 | 说明 |
|----------|------|------|
| `meeting_id` | string | 会议唯一标识符 |

### 4.2 通信协议

**建立连接后服务端推送**：

```json
{
  "type": "connected",
  "meeting_id": "my-meeting-001",
  "message": "会议助手已连接，发送音频数据开始录制"
}
```

**客户端发送音频帧（二进制）**：

```
<raw audio bytes>
```

每帧收到后服务端回复：

```json
{
  "type": "recording",
  "buffer_size": 1048576
}
```

**客户端发送停止/控制报文（JSON 文本）**：

```json
{"type": "stop"}
```

服务端处理完成后依次推送：

```json
// 1. 开始处理
{"type": "processing", "message": "正在处理音频，请稍候..."}

// 2. 转写结果
{"type": "transcript", "data": {"segments": [...], "language": "zh", "source": "asr"}}

// 3. 说话人分离结果
{"type": "diarization", "data": {
  "transcript": "完整转录文本",
  "diarized_transcript": "带说话人标签的文本",
  "num_speakers": 4,
  "speakers": ["张总", "李明", "王芳", "赵伟"]
}}

// 4. 摘要 Agent 结果
{"type": "summary", "data": {"title": "会议纪要", "topics": [...], ...}}

// 5. 行动项 Agent 结果
{"type": "actions", "data": {"action_items": [...], ...}}

// 6. 洞察 Agent 结果
{"type": "insights", "data": {"overall_sentiment": "positive", ...}}

// 7. 完成
{"type": "completed", "data": {"meeting_id": "xxx", "status": "COMPLETED", "errors": []}}
```

**演示模式**（无需真实音频，使用内置示例数据）：

```json
{"type": "demo"}
```

**心跳**：

```json
{"type": "ping"}
```

服务端回复：

```json
{"type": "pong"}
```

---

## 六、处理参数说明

### 6.1 降噪级别（denoise_level）

| 级别 | 说明 | 适用场景 |
|------|------|----------|
| 0 | 关闭降噪 | 录音质量极好，无需处理 |
| 1 | 轻度降噪（默认） | 普通办公环境 |
| 2 | 中度降噪 | 较嘈杂环境（咖啡厅、开放工位） |
| 3 | 重度降噪 | 极端嘈杂环境（工厂、户外） |

### 5.2 输入源优先级

当同时提供多个输入源时，优先级为：`file_id` > `file_path` > `url`

### 5.3 转写引擎选择（通过 ASR_ENGINE 环境变量）

| 引擎 | 说明 | 推荐场景 |
|------|------|----------|
| `auto` | 自动探测（默认） | 中文用 FunASR，非中文用 Faster-Whisper |
| `funasr` | 阿里 FunASR | 低配 CPU、纯中文场景 |
| `faster_whisper` | Faster-Whisper | GPU 加速、多语言场景 |
| `sensevoice` | SenseVoice | 多语言、高精度 |
| `openai` | OpenAI Whisper API | 云端处理 |
| `groq` | Groq Whisper API | 云端超快速处理 |

---

## 七、错误码说明

| HTTP 状态码 | 说明 | 常见原因 |
|-------------|------|----------|
| 200 | 成功 | - |
| 400 | 请求参数错误 | 未提供 file_id/file_path/url，文件路径不在允许范围 |
| 404 | 资源未找到 | 上传文件 ID 无效，本地文件路径不存在 |
| 422 | 参数校验失败 | 参数类型错误或缺失 |
| 500 | 服务器内部错误 | LLM API 不可用，ASR 转录失败，外部集成异常 |

**错误响应格式**：

```json
{
  "detail": "错误描述信息"
}
```