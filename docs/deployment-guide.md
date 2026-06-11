# SmartMeet 部署与运行指南

## 一、环境需求

| 依赖项 | 最低版本 | 说明 |
|--------|----------|------|
| Python | 3.11+ | 核心运行环境 |
| Redis | 6.0+ | Arq 异步任务队列核心底座（必需） |
| CUDA | 12.1 | GPU 加速（可选，CPU 模式也可运行但较慢） |
| FFmpeg | 4.4+ | 音视频处理 |
| Node.js | 18+ | 前端控制台（可选） |

---

## 二、Miniconda 环境搭建（推荐）

### 2.1 安装 Miniconda

从 [Miniconda 官方页面](https://docs.conda.io/en/latest/miniconda.html) 下载并安装 Python 3.11 版本。

### 2.2 基于 environment.yml 创建环境

```bash
# 一键创建包含所有依赖的 conda 环境
conda env create -f environment.yml

# 激活环境
conda activate smartmeet
```

`environment.yml` 已固化以下关键依赖版本：
- Python 3.11
- PyTorch 2.1+（CUDA 12.1 加速）
- FFmpeg 4.4+
- Faster-Whisper / WhisperX / PyAnnote / FunASR（语音处理）
- LangGraph / LangChain（流水线框架）
- FastAPI / Uvicorn（API 网关）
- WeasyPrint（PDF 渲染）
- yt-dlp（音视频下载）

### 2.3 手动创建（自定义）

```bash
conda create -n smartmeet python=3.11
conda activate smartmeet

# 安装 PyTorch（GPU 版）
conda install pytorch torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia

# 安装 FFmpeg
conda install ffmpeg -c conda-forge

# 安装 Python 依赖
pip install -e .
```

---

## 三、配置文件

### 3.1 环境变量

复制环境变量模板并填写真实凭证：

```bash
cp .env.example .env
```

关键配置项说明：

| 环境变量 | 必需 | 说明 |
|----------|------|------|
| `LLM_API_KEY` | **是** | 大模型 API 密钥（OpenAI/DeepSeek 等） |
| `LLM_BASE_URL` | 推荐 | API 端点（默认 OpenAI） |
| `LLM_MODEL` | 推荐 | 模型名称（默认 gpt-4o-mini） |
| `HF_TOKEN` | 推荐 | HuggingFace Token（PyAnnote 声纹模型必需） |
| `ASR_ENGINE` | 否 | 转写引擎偏好（auto/funasr/faster_whisper/sensevoice） |
| `WHISPER_MODEL_SIZE` | 否 | Whisper 模型大小（默认 large-v3） |
| `WHISPER_DEVICE` | 否 | 运行设备（cuda/cpu） |
| `FEISHU_APP_ID` | 否 | 飞书应用凭证（不配置则跳过飞书分发） |
| `FEISHU_APP_SECRET` | 否 | 飞书应用密钥 |
| `FEISHU_RECEIVE_ID` | 否 | 飞书群聊 ID |
| `JIRA_SERVER` | 否 | Jira 服务器地址（不配置则跳过 Jira 同步） |
| `JIRA_EMAIL` | 否 | Jira 登录邮箱 |
| `JIRA_API_TOKEN` | 否 | Jira API Token |
| `NOTEKING_PROXY` | 否 | 网络代理（国内访问 YouTube 等） |
| `BILIBILI_SESSDATA` | 否 | B站 Cookie（用于下载高清视频） |

### 3.2 验证配置

```bash
# 确认环境变量已正确加载
python -c "import os; print('LLM_API_KEY:', os.getenv('LLM_API_KEY', '❌ 未设置'))"
```

---

## 四、快速启动

### 4.1 启动 API 服务（核心服务）

```bash
conda activate smartmeet
python -m api.main
```

服务默认监听 `http://0.0.0.0:8000`。

验证服务状态：

```bash
curl http://localhost:8000/health
# 返回: {"status": "ok"}
```

交互式 API 文档：

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 4.2 启动 Web 前端控制台（可选）

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:3000`。

### 4.3 使用 CLI 命令行客户端（可选）

```bash
# 处理本地文件
python -m cli.main process /path/to/meeting.mp4 -c "Q3 预算评审会议"

# 处理在线视频
python -m cli.main run https://www.bilibili.com/video/BV1xx411c7mD

# 纯交付分发（渲染排版、建任务、发飞书）
python -m cli.main deliver /path/to/final_result.json --sync-tasks

# 附加自定义配置 (JobConfig)
# 可以直接传递 JSON 字符串，也可以传递 JSON 文件的路径
python -m cli.main process /path/to/meeting.mp4 --config '{"feishu": {"enabled": false}}'
python -m cli.main run https://bilibili... --config ./my_config.json
```

CLI 通过环境变量 `SMARTMEET_API` 指定 API 服务地址（默认 `http://127.0.0.1:8000`）。

---

## 五、API 接口速览

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务根信息 |
| `/health` | GET | 健康检查 |
| `/docs` | GET | Swagger 交互式文档 |
| `/api/v1/recording/upload` | POST | 上传音视频文件 |
| `/api/v1/recording/process` | POST | 离线处理（非流式） |
| `/api/v1/recording/process/async`| POST | 离线处理（纯异步后台任务） |
| `/api/v1/recording/process/stream` | POST | 离线处理（SSE 流式） |
| `/api/v1/analyze` | POST | 原子化分析接口（纯 JSON 输出） |
| `/api/v1/render` | POST | 原子化渲染与外部分发接口 |
| `/api/v1/tasks/{task_id}` | GET | 异步任务轮询查询接口 |
| `/api/v1/config` | GET/PUT | 系统配置读取与更新接口 |
| `/api/v1/reports` | GET/DELETE | 历史报告管理接口 |
| `/ws/meeting/{meeting_id}` | WebSocket | 实时录音与并发节点 处理 |

详细接口文档见 [api-reference.md](api-reference.md)。

---

## 六、运行模式说明

### 6.1 离线文件处理模式

```bash
# Step 1: 上传文件
curl -X POST http://localhost:8000/api/v1/recording/upload \
  -F "file=@/path/to/meeting.mp4"

# 返回: {"file_id": "abc123", "filename": "meeting.mp4", ...}

# Step 2: 提交处理（带 SSE 进度推送）
curl -X POST http://localhost:8000/api/v1/recording/process/stream \
  -d "file_id=abc123&context=Q3预算评审会议&denoise_level=1"
```

### 6.2 在线链接处理模式

```bash
# 直接提交视频链接处理
curl -X POST http://localhost:8000/api/v1/recording/process \
  -d "url=https://www.youtube.com/watch?v=xxxxx&context=AI技术分享"
```

### 6.3 实时录音模式

通过 WebSocket 连接 `ws://localhost:8000/ws/meeting/my-meeting-001`，然后：
1. 持续发送音频二进制帧
2. 发送 `{"type": "stop"}` 触发处理
3. 接收各节点 的实时分析结果

---

## 七、外部集成配置

### 7.1 飞书（Lark）集成

1. 在 [飞书开放平台](https://open.feishu.cn) 创建自建应用
2. 获取 `App ID` 和 `App Secret`
3. 在应用权限中开启：`im:message`, `im:resource`（发送消息与文件）
4. 将应用添加至目标群聊
5. 配置 `.env` 中的 `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_RECEIVE_ID`

> 飞书 Webhook 机器人仅支持推送图文消息卡片，不支持发送 PDF 附件。如需发送 PDF 附件，必须使用自建应用的 Open API。

### 7.2 Jira Cloud 集成

1. 登录 [Atlassian](https://id.atlassian.com)
2. 进入账号安全设置，生成 API Token
3. 配置 `.env` 中的 `JIRA_SERVER`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`

### 7.3 本地语音引擎说明

| 引擎 | 场景 | 配置 |
|------|------|------|
| FunASR | 中文场景、低配 CPU | `ASR_ENGINE=funasr` |
| Faster-Whisper | 通用场景、GPU 加速 | `ASR_ENGINE=faster_whisper` |
| SenseVoice | 多语言场景 | `ASR_ENGINE=sensevoice` |
| auto（默认） | 自动探测 | 中文用 FunASR，非中文用 Faster-Whisper |

---

## 八、测试

```bash
conda activate smartmeet

# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_schema_contracts.py -v
python -m pytest tests/test_followup_workflow_integration.py -v
```

---

## 九、常见问题

### Q: 启动时提示 LLM_API_KEY 未配置？

A: 必须配置至少一个 LLM 厂商的 API Key。复制 `.env.example` 为 `.env`，填写 `LLM_API_KEY`。

### Q: 说话人分离（Diarization）报错？

A: 需配置 `HF_TOKEN` 并在 HuggingFace 上同意 [PyAnnote 模型协议](https://huggingface.co/pyannote/speaker-diarization-3.1)。

### Q: 如何处理 YouTube 视频下载失败？

A: 国内环境需配置网络代理 `NOTEKING_PROXY=socks5://127.0.0.1:7890`。

### Q: GPU 显存不足怎么办？

A: 可以改用 CPU 模式（`WHISPER_DEVICE=cpu`）或使用更小的 Whisper 模型（`WHISPER_MODEL_SIZE=small`）。