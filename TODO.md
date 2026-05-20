# Smartmeet Agent Suite 融合重构计划

## 阶段一：项目骨架初始化
- [x] 确定项目名称为 Smartmeet Agent Suite
- [x] 创建新的工作根目录 `smartmeet-agent-suite`
- [x] TODO 1: 初始化项目骨架与统一依赖。合并两边的 Python 依赖环境，确保核心音视频处理与 LangGraph 环境相互兼容。
- [x] TODO 2: 建立标准化的基础目录结构（如 `api`, `agents`, `services` 等）。
- [x] TODO 2.5: Miniconda 环境标准化与 .gitignore。输出标准的 `conda create` 运行指令或 `environment.yml`，固化 ffmpeg 和底层科学计算库的依赖版本，体现系统的标准交付能力。

## 阶段二：核心模块抽离与迁移
- [x] TODO 3: 提取多智能体中枢。将 `multi-agent-meeting-assistant-main/python` 目录下的 LangGraph 工作流逻辑和各个 Agent（Summary, Action, Insight, FollowUp）以及第三方集成接入迁移到新目录，提供标准架构设计说明。
- [x] TODO 4: 提取离线媒体处理与生成引擎。将 `noteking-pro-main` 中的降噪、说话人分离处理逻辑，以及丰富版式生成（LaTeX PDF、Mermaid 思维导图）抽离到新目录的服务层。
- [x] TODO 4.5: 模板与工作流重构解耦。剥离 PDF 内置 CSS/LaTeX 模板至 `assets/` 目录；将 `meeting_graph.py` 重构为 `workflows/meeting_workflow.py` 并清理 `agents/` 包，完全符合 Fail-Fast 与拒绝过度兼容原则。

## 阶段二半：模块独立性加固（阶段三前置）
- [x] 审计 CODE_REVIEW_MODULE_INDEPENDENCE.md，补充 5 处遗漏（mindmap_engine、门面穿透、PDFPipeline LLM 硬编码、FollowUpAgent 耦合预警、LLM 注入统一）
- [x] 修复 `pdf_engine.py` 门面穿透问题（`_get_duration` → `get_duration`）
- [x] 新建 `schemas/meeting_schemas.py`，引入 Pydantic 数据契约层（SummaryOutput/ActionOutput/InsightOutput/FollowUpOutput）
- [x] 更新 AGENTS.md，补充模块边界约束、LLM 注入规范、依赖方向约束、Schema-First 原则
- [x] 拆分 ActionAgent：提取逻辑保留在 Agent，外部同步抽离至 `services/integrations/action_sync.py`
- [x] FollowUpAgent 引入 `_adapt_upstream()` 标准化适配层，通过 Schema 隔离上游格式变化
- [x] 补充 15 个契约测试（`tests/test_schema_contracts.py`），全部通过
- [x] 补充 `pytest` 开发依赖至 `environment.yml` 和 `pyproject.toml`

## 阶段三：流程缝合与闭环改造
- [ ] TODO 5: 拓展全渠道输入网关。在 API 层增加离线任务入口（本地音视频文件/在线URL），经过预处理降噪、ASR语音转录、说话人分割与关键帧提取对齐后喂给 LangGraph 状态机。
  - [ ] 5.1: 在 [api/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/api) 目录下新建 FastAPI 核心骨架 `main.py` 及路由模块。
  - [ ] 5.2: 迁移 `noteking-pro` 的 `/api/v1/recording/upload` 接口，支持本地音视频文件上传到临时目录。
  - [ ] 5.3: 迁移 `noteking-pro` 的音视频在线链接抓取（支持 Bilibili/YouTube）与转录提取逻辑。
  - [ ] 5.4: 在 [api/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/api) 层实现统一的音视频预处理流水线（降噪 -> ASR转录 -> 说话人分割 -> 帧提取），并与 [workflows/meeting_workflow.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/workflows/meeting_workflow.py) 中的 LangGraph 状态机无缝对接。
  - [ ] 5.5: 合并实时 WebSocket 接口 `/ws/meeting/{meeting_id}`，确保能够实时录音并自动流式调用转录与多 Agent 状态机。
- [ ] TODO 6: 改造资产生成与分发节点。升级原有的 Follow-up Agent，使其能够调用生成引擎打包 PDF 和思维导图附件，并通过飞书/Jira完成执行流的硬闭环。
  - [ ] 6.1: 改造 [agents/followup_agent.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/agents/followup_agent.py)，在 `process` 方法中引入 [services/document_engine/pdf_engine.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/document_engine/pdf_engine.py) 与 [services/document_engine/mindmap_engine.py](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/document_engine/mindmap_engine.py)。
  - [ ] 6.2: 集成 LaTeX PDF 讲义渲染与 Mermaid 思维导图自动生成，渲染出精美的最终资产并保存到输出目录。
  - [ ] 6.3: 升级 Feishu 与 Jira 客户端，支持将生成的 PDF 报告与思维导图文件以附件形式上传到飞书群（通过机器人/Webhook）与 Jira 对应 Issue（待办事项）中。
- [ ] TODO 6.5: 多端网关适配（Omni-channel Entry）。保留并改造原有的 `web/` (前端控制台)、`cli/` (命令行)、`mcp/` (大模型上下文协议) 等“壳”，将其全部对接到统一的 API 层，体现架构的“多端解耦”能力。
  - [ ] 6.5.1: 迁移并适配 [web/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/web) 前端控制台页面，将原有的 API 端点修改指向缝合后的统一 FastAPI 服务端口（8000），解决跨域与上传逻辑适配。
  - [ ] 6.5.2: 迁移并适配 [cli/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/cli) 命令行客户端，确保能通过 CLI 直接提交离线任务并接收报告。
  - [ ] 6.5.3: 迁移并适配 [mcp/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/mcp) 大模型上下文协议服务器，使外部大模型能够以 Tool 形式调用该套件的能力。

## 阶段四：售前包装与文档迁移
- [x] TODO 7: 统一配置管理（整合相关的环境变量和配置解析，将原 MiniMax 客户端重构为通用 OpenAI 兼容客户端，以适配 Cloudflare Workers AI 等多模态 LLM 厂商）。
  - [x] 7.1: 重构 `minimax_client.py` 变为通用的 `openai_client.py`，使用标准 `openai` 客户端，适配 DeepSeek, OpenAI, MiniMax 等多模态大语言模型。
  - [x] 7.2: 在 [services/integrations/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/services/integrations) 中对各个 Agent (Summary, Action, Insight) 调用的 client 进行通用化替换。
  - [x] 7.3: 细化 [.env](file:///d:/Workspace/agent-project/smartmeet-agent-suite/.env) 中的环境变量说明，统一配置源。
- [ ] TODO 8: 文档融合与重构。将两个项目的 `docs` 目录完整迁移到新项目，整合 API 文档、架构图，并针对融合后的系统修改八股文和从零教程。
  - [ ] 8.1: 迁移 `multi-agent` 和 `noteking` 的所有 md 说明文档至 [docs/](file:///d:/Workspace/agent-project/smartmeet-agent-suite/docs)。
  - [ ] 8.2: 撰写统一的架构设计图（使用 Mermaid 图表展示多 Agent 会议协作与音视频流水线的闭环关系）。
  - [ ] 8.3: 补充融合后的系统部署、运行指南及 API 文档说明。
- [ ] TODO 9: 撰写全新的 `README.md`，重点突显“企业级全场景知识闭环”的业务价值，作为简历上的核心抓手。
  - [ ] 9.1: 重构主 [README.md](file:///d:/Workspace/agent-project/smartmeet-agent-suite/README.md)，移除临时开发备注，采用极具吸引力的视觉文案进行包装。
  - [ ] 9.2: 细化项目功能清单与一键启动指南，展示 Miniconda 环境下的完整部署与运行案例。

