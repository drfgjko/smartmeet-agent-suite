# SmartMeet Agent Suite 架构设计

## 一、系统概述

SmartMeet Agent Suite 是一个企业级多模态智能会议与全链路协同 Agent 解决方案。它通过 **LangGraph 多智能体编排** 与 **音视频媒体处理引擎** 的深度融合，实现从原始音视频输入到结构化报告、待办同步、资产分发的全自动化闭环。

### 核心设计原则

- **Pipeline + Fan-out/Fan-in 编排**：媒体处理阶段严格串行（Pipeline），Agent 分析阶段并行执行（Fan-out），最终汇聚到 Follow-Up Agent（Fan-in）。
- **Schema-First 数据契约**：Agent 间传递的结构化数据通过 Pydantic 模型定义，模块边界从"约定"变为"接口"约束。
- **LLM 客户端统一注入**：所有 Agent 统一通过构造函数注入由 `create_llm_client()` 工厂创建的客户端，支持 OpenAI/DeepSeek/MiniMax/Cloudflare Workers AI 等多厂商。
- **Fail-Fast 与显式降级**：核心链路失败直接报错；非核心链路降级时记录显式日志和状态标记，禁止静默失败。

---

## 二、顶层架构图

```mermaid
graph TB
    %% ===== 输入层 =====
    subgraph Input["输入渠道 / Input Channels"]
        A1["本地音视频文件<br/>(MP4/MP3/WAV/M4A)"]
        A2["在线视频链接<br/>(B站/YouTube)"]
        A3["实时录音流<br/>(WebSocket)"]
    end

    %% ===== API 网关层 =====
    subgraph API["API 网关 / FastAPI"]
        B1["REST API<br/>/api/v1/recording/*"]
        B2["WebSocket<br/>/ws/meeting/{id}"]
        B3["SSE 流式推送<br/>Server-Sent Events"]
    end

    %% ===== 媒体处理引擎 =====
    subgraph Media["离线媒体处理引擎 / Media Engine"]
        C1["预处理 Preprocessor<br/>降噪·提取音轨·元信息"]
        C2["语言检测 Language<br/>自动识别中/英文"]
        C3["ASR 转录 Transcriber<br/>Whisper/FunASR/SenseVoice"]
        C4["说话人分离 Diarizer<br/>PyAnnote 声纹识别"]
        C5["关键帧提取 Keyframes<br/>场景检测·字幕对齐"]
    end

    %% ===== 多 Agent 核心层 =====
    subgraph Agents["多 Agent 协作层 / LangGraph"]
        D0["状态图 StateGraph<br/>MeetingGraphState"]
        D1["Summary Agent<br/>结构化摘要"]
        D2["Action Agent<br/>待办提取·外部同步"]
        D3["Insight Agent<br/>发言洞察·情绪分析"]
        D4["Follow-Up Agent<br/>(Fan-in 汇聚)"]
    end

    %% ===== 文档与服务层 =====
    subgraph Services["服务层 / Services"]
        E1["ReportComposer<br/>报告组装·关键帧排版"]
        E2["ReportRenderer<br/>LaTeX PDF / HTML 双轨渲染"]
        E3["MindMapService<br/>Mermaid 思维导图"]
        E4["ReportDelivery<br/>飞书/Jira 分发"]
    end

    %% ===== 输出层 =====
    subgraph Output["资产输出 / Output"]
        F1["Markdown 报告"]
        F2["LaTeX PDF 讲义"]
        F3["HTML 网页版"]
        F4["Mermaid 思维导图"]
        F5["飞书群聊 · Jira Issue"]
    end

    %% ===== 多端网关 =====
    subgraph Gateways["多端接入网关"]
        G1["Web 控制台<br/>Next.js (port 3000)"]
        G2["CLI 命令行客户端<br/>smartmeet process/run"]
        G3["MCP 协议服务器<br/>大模型上下文协议"]
    end

    %% ===== 连接关系 =====
    A1 --> B1
    A2 --> B1
    A3 --> B2
    B1 --> B3
    B1 --> Media
    B2 --> Media

    C1 --> C2 --> C3 --> C4
    C4 --> D0
    C5 --> D0

    D0 --> D1 & D2 & D3
    D1 & D2 & D3 --> D4

    D4 --> E1 --> E2 --> E4
    D4 --> E3

    E2 --> F1 & F2 & F3
    E3 --> F4
    E4 --> F5

    G1 --> B1
    G2 --> B1
    G3 --> B1
```

---

## 三、模块职责

### 3.1 API 网关层 `api/`

| 模块 | 职责 |
|------|------|
| [api/main.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/api/main.py) | FastAPI 入口，注册路由、CORS 中间件、静态文件服务 |
| [api/routes/recording.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/api/routes/recording.py) | 音视频处理核心入口：文件上传、离线处理（含流式进度推送与异步后台任务） |
| [api/routes/analyze.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/api/routes/analyze.py) | 原子化分析接口：仅运行 AI Agent 提取摘要、待办和洞察（不含音视频处理与排版） |
| [api/routes/render.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/api/routes/render.py) | 原子化渲染接口：根据分析结果排版生成 PDF/Markdown/思维导图报告及触发分发 |
| [api/routes/tasks.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/api/routes/tasks.py) | 异步任务管理：用于轮询查询离线异步处理任务状态 |
| [api/routes/websocket.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/api/routes/websocket.py) | 实时录音 WebSocket 接口，接收音频流并触发完整流水线 |

### 3.2 媒体处理引擎 `services/media_engine/`

| 模块 | 职责 |
|------|------|
| [preprocessor.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/media_engine/preprocessor.py) | 音频降噪、音轨提取、时长与视频元信息获取 |
| [transcriber.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/media_engine/transcriber.py) | ASR 语音识别（支持 Faster-Whisper / FunASR / SenseVoice 多引擎） |
| [diarizer.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/media_engine/diarizer.py) | 说话人声纹分离（PyAnnote），将文本按发言人分段对齐 |
| [frames.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/media_engine/frames.py) | 基于场景检测的关键帧提取 + 字幕时间线对齐 |
| [downloader.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/media_engine/downloader.py) | yt-dlp 封装，支持 YouTube/Bilibili 等平台的音视频下载 |
| [parser.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/media_engine/parser.py) | 在线链接解析，识别平台类型与资源格式 |

### 3.3 多 Agent 协作层 `agents/` + `workflows/`

| 模块 | 职责 |
|------|------|
| [workflows/meeting_workflow.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/workflows/meeting_workflow.py) | LangGraph `StateGraph` 编排定义：Fan-out 并行 + Fan-in 汇聚 |
| [agents/summary_agent.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/agents/summary_agent.py) | 从转写文本生成结构化会议纪要（议题、讨论要点、结论、决策） |
| [agents/action_agent.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/agents/action_agent.py) | 提取行动项（谁/做什么/截止时间），委托 `action_sync` 同步至 Jira/飞书 |
| [agents/insight_agent.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/agents/insight_agent.py) | 发言统计、情绪分析、效率评分、关键词提取 |
| [agents/speaker_inference_agent.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/agents/speaker_inference_agent.py) | 根据对话上下文推断匿名发言人的真实姓名，执行全局身份替换 |
| [agents/followup_agent.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/agents/followup_agent.py) | Fan-in 汇聚节点，调用服务层生成报告/思维导图并分发 |
| [schemas/meeting_schemas.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/schemas/meeting_schemas.py) | Pydantic 数据契约层，定义 Agent 间传递的结构化数据类型 |

### 3.4 服务层 `services/`

| 模块 | 职责 |
|------|------|
| [services/pipeline/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/pipeline/) | 应用编排层：分 `offline_processor.py` (离线处理) 和 `online_processor.py` (流式处理)，统一调度媒体引擎与工作流 |
| [services/task_queue.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/task_queue.py) & [task_service.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/task_service.py) | 异步任务处理队列与状态持久化管理，支持基于后台 Task 的可靠投递 |
| [services/checkpoint_service.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/checkpoint_service.py) | 分析及渲染产物进度存储，用于解耦各个 Pipeline 阶段的数据持久化 |
| [services/integrations/llm_client.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/integrations/llm_client.py) | 统一 LLM 客户端（OpenAI 兼容），支持异步/同步/流式调用 |
| [services/integrations/jira_client.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/integrations/jira_client.py) | Jira Cloud REST API 集成 |
| [services/integrations/feishu_client.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/integrations/feishu_client.py) | 飞书 Open API 集成（消息推送/文件上传） |
| [services/integrations/action_sync.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/integrations/action_sync.py) | 行动项幂等同步（从 ActionAgent 拆分出的外部同步逻辑） |
| [services/document_engine/pdf_engine.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/document_engine/pdf_engine.py) | LaTeX PDF + HTML 双引擎排版渲染 |
| [services/document_engine/mindmap_engine.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/document_engine/mindmap_engine.py) | Mermaid 思维导图生成引擎 |
| [services/reporting/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/reporting/) | 报告组装（ReportComposer）、渲染（ReportRenderer）、脑图（MindMapService） |
| [services/delivery/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/delivery/) | 多渠道分发服务（飞书群聊/Jira Issue 附件挂载及通用 Webhook） |

### 3.5 多端网关

| 模块 | 职责 | 技术栈 |
|------|------|--------|
| [web/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/web/) | 前端控制台 | Next.js 14 + React + TailwindCSS |
| [cli/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/cli/) | 命令行客户端 | Python Click + Rich |
| [mcp/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/mcp/) | MCP 协议服务器 | TypeScript + @modelcontextprotocol/sdk |

---

## 四、核心数据流

### 4.1 离线文件/链接处理流程

```mermaid
sequenceDiagram
    participant Client as 客户端 (Web/CLI/MCP)
    participant API as FastAPI
    participant App as ApplicationService
    participant Media as MediaEngine
    participant Graph as LangGraph
    participant Services as Reporting & Delivery

    Client->>API: POST /api/v1/recording/process
    API->>App: run_offline_pipeline()
    
    App->>Media: preprocess() 降噪+音轨提取
    App->>Media: detect_language() 语言检测
    App->>Media: transcribe() ASR 转录
    App->>Media: diarize() 说话人分离
    App->>Media: extract_keyframes() 关键帧提取

    App->>Graph: run_meeting_pipeline()
    
    par Summary Agent
        Graph->>Graph: 结构化摘要生成
    and Action Agent
        Graph->>Graph: 行动项提取+外部同步
    and Insight Agent
        Graph->>Graph: 发言洞察+情绪分析
    end

    Graph->>Graph: Follow-Up Agent 汇聚
    Graph->>Services: 报告组装+渲染
    Graph->>Services: 思维导图生成
    Graph->>Services: 飞书/Jira 分发

    App->>API: 返回完整结果
    API->>Client: JSON 响应
```

### 4.2 实时录音 WebSocket 流程

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant WS as WebSocket
    participant App as ApplicationService
    participant Media as MediaEngine
    participant Graph as LangGraph

    Client->>WS: 连接 /ws/meeting/{id}
    WS->>Client: 确认连接
    
    loop 音频流
        Client->>WS: 二进制音频帧
        WS->>WS: 缓冲音频数据
        WS->>Client: buffer_size 确认
    end

    Client->>WS: {"type": "stop"}
    WS->>App: process_audio_capture()
    
    App->>Media: 预处理 → 转录 → 说话人分离
    App->>Graph: run_meeting_pipeline()
    
    Graph-->>WS: 实时推送各 Agent 结果
    WS->>Client: {"type": "summary", ...}
    WS->>Client: {"type": "actions", ...}
    WS->>Client: {"type": "insights", ...}
    WS->>Client: {"type": "completed", ...}
```

---

## 五、Agent 协作模式

```mermaid
graph LR
    subgraph Pipeline["Pipeline 阶段"]
        Input["输入音视频"] --> Pre["预处理/降噪"]
        Pre --> ASR["ASR 转录"]
        ASR --> Diar["说话人分离"]
        Diar --> Frames["关键帧提取"]
    end

    subgraph FanOut["Fan-Out 并行阶段"]
        S1["Summary Agent<br/>结构化摘要"]
        S2["Action Agent<br/>待办提取+同步"]
        S3["Insight Agent<br/>发言洞察+情绪"]
    end

    subgraph FanIn["Fan-In 汇聚阶段"]
        FU["Follow-Up Agent<br/>报告组装+渲染+分发"]
    end

    Frames --> S1 & S2 & S3
    S1 & S2 & S3 --> FU
    
    FU --> MD["Markdown 报告"]
    FU --> PDF["LaTeX PDF 讲义"]
    FU --> HTML["HTML 网页版"]
    FU --> MM["Mermaid 思维导图"]
    FU --> DS["飞书/Jira 分发"]
```

### Agent 间数据契约

| 数据模型 | 来源 Agent | 消费方 | 核心字段 |
|----------|-----------|--------|----------|
| [SummaryOutput](file:///d:/Workspace/agent-project/smartmeet-agent-suite/schemas/meeting_schemas.py#L24-L31) | SummaryAgent | FollowUpAgent | title, date, participants, topics, decisions, next_steps |
| [ActionOutput](file:///d:/Workspace/agent-project/smartmeet-agent-suite/schemas/meeting_schemas.py#L50-L54) | ActionAgent | FollowUpAgent | meeting_id, action_items, sync_status |
| [InsightOutput](file:///d:/Workspace/agent-project/smartmeet-agent-suite/schemas/meeting_schemas.py#L66-L74) | InsightAgent | FollowUpAgent | overall_sentiment, speaker_stats, efficiency_score, keywords |
| [FollowUpOutput](file:///d:/Workspace/agent-project/smartmeet-agent-suite/schemas/meeting_schemas.py#L100-L103) | FollowUpAgent | API 响应 | meeting_id, artifacts, delivery_results |

---

## 六、LLM 客户端统一注入

所有 Agent 通过构造函数接收统一的 `UnifiedLLMClient` 实例，由工厂方法 `create_llm_client()` 创建：

```python
from services.integrations.llm_client import create_llm_client

llm = create_llm_client(
    api_key="sk-xxx",          # 默认从 LLM_API_KEY 环境变量读取
    base_url="https://...",    # 默认从 LLM_BASE_URL 读取
    model="gpt-4o-mini",       # 默认从 LLM_MODEL 读取
)
```

**支持的厂商**：
- OpenAI (`gpt-4o`, `gpt-4o-mini`)
- DeepSeek (`deepseek-chat`)
- MiniMax (需配置 `MINIMAX_GROUP_ID`)
- Cloudflare Workers AI (`@cf/meta/llama-3-8b-instruct`)

---

## 七、多端接入架构

```mermaid
graph TB
    Web["Web 前端控制台<br/>localhost:3000"]
    CLI["CLI 命令行工具<br/>smartmeet process/run"]
    MCP["MCP 协议服务器<br/>大模型 Tool 调用"]
    
    API["FastAPI 统一网关<br/>localhost:8000"]
    
    Web -->|HTTP/SSE| API
    CLI -->|HTTP/SSE| API
    MCP -->|HTTP| API
    
    API --> Services["后端服务层"]
```

三种接入方式共享同一套后端服务，体现"多端解耦"设计理念。

---

## 八、目录结构总览

```
smartmeet-agent-suite/
├── api/                        # FastAPI 网关层
│   ├── main.py                 # 入口与路由注册
│   └── routes/
│       ├── analyze.py          # 原子化分析 API
│       ├── recording.py        # 核心入口：离线处理及任务分发
│       ├── render.py           # 原子化渲染 API
│       ├── tasks.py            # 异步任务查询 API
│       └── websocket.py        # 实时录音 WebSocket
├── agents/                     # 多 Agent 协作层
│   ├── summary_agent.py        # 摘要 Agent
│   ├── action_agent.py         # 待办 Agent
│   ├── insight_agent.py        # 洞察 Agent
│   ├── speaker_inference_agent.py # 发言人推断 Agent
│   └── followup_agent.py       # 跟进 Agent（Fan-in 汇聚）
├── workflows/
│   └── meeting_workflow.py     # LangGraph 状态图编排
├── schemas/
│   └── meeting_schemas.py      # Pydantic 数据契约
├── services/                   # 服务层
│   ├── pipeline/               # 应用编排管线 (offline_processor, online_processor)
│   ├── task_queue.py           # 异步任务队列服务
│   ├── task_service.py         # 任务管理服务
│   ├── checkpoint_service.py   # 状态数据持久化服务
│   ├── media_engine/           # 媒体处理引擎
│   │   ├── preprocessor.py     # 降噪/提取音轨
│   │   ├── transcriber.py      # ASR 语音识别
│   │   ├── diarizer.py         # 说话人分离
│   │   ├── frames.py           # 关键帧提取
│   │   ├── downloader.py       # 音视频下载
│   │   └── parser.py           # 链接解析
│   ├── document_engine/        # 文档生成引擎
│   │   ├── pdf_engine.py       # LaTeX/HTML 排版
│   │   └── mindmap_engine.py   # 思维导图
│   ├── integrations/           # 第三方集成
│   │   ├── llm_client.py       # 统一 LLM 客户端
│   │   ├── jira_client.py      # Jira 集成
│   │   ├── feishu_client.py    # 飞书集成
│   │   └── action_sync.py      # 行动项同步
│   ├── reporting/              # 报告组装与渲染
│   └── delivery/               # 多渠道分发
├── cli/                        # CLI 命令行客户端
│   └── main.py
├── web/                        # Web 前端控制台
│   ├── src/app/page.tsx
│   └── package.json
├── mcp/                        # MCP 协议服务器
│   ├── src/index.ts
│   └── package.json
├── assets/                     # CSS/LaTeX 模板文件
├── tests/                      # 测试套件
├── docs/                       # 文档
├── .env.example                # 环境变量模板
├── environment.yml             # Conda 环境依赖
└── pyproject.toml              # Python 项目配置
```