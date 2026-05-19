# Smartmeet Agent Suite 融合重构计划

## 阶段一：项目骨架初始化
- [x] 确定项目名称为 Smartmeet Agent Suite
- [x] 创建新的工作根目录 `smartmeet-agent-suite`
- [x] TODO 1: 初始化项目骨架与统一依赖。合并两边的 Python 依赖环境，确保核心音视频处理与 LangGraph 环境相互兼容。
- [x] TODO 2: 建立标准化的基础目录结构（如 `api`, `core`, `agents`, `services` 等）。
- [x] TODO 2.5: Miniconda 环境标准化与 .gitignore。输出标准的 `conda create` 运行指令或 `environment.yml`，固化 ffmpeg 和底层科学计算库的依赖版本，体现系统的标准交付能力。

## 阶段二：核心模块抽离与迁移
- [x] TODO 3: 提取多智能体中枢。将 `multi-agent-meeting-assistant-main/python` 目录下的 LangGraph 工作流逻辑和各个 Agent（Summary, Action, Insight, FollowUp）以及第三方集成接入迁移到新目录，补充标准架构及面试注释。
- [x] TODO 4: 提取离线媒体处理与生成引擎。将 `noteking-pro-main` 中的降噪、说话人分离处理逻辑，以及丰富版式生成（LaTeX PDF、Mermaid 思维导图）抽离到新目录的服务层。
- [x] TODO 4.5: 模板与工作流重构解耦。剥离 PDF 内置 CSS/LaTeX 模板至 `assets/` 目录；将 `meeting_graph.py` 重构为 `workflows/meeting_workflow.py` 并清理 `agents/` 包，完全符合 Fail-Fast 与拒绝过度兼容原则。

## 阶段三：流程缝合与闭环改造
- [ ] TODO 5: 拓展全渠道输入网关。在 API 层增加离线任务入口（本地音视频文件/在线URL），经过降噪处理后喂给 LangGraph 状态机。
- [ ] TODO 6: 改造资产生成与分发节点。升级原有的 Follow-up Agent，使其能够调用生成引擎打包 PDF 和思维导图附件，并通过飞书/Jira完成执行流的硬闭环。
- [ ] TODO 6.5: 多端网关适配（Omni-channel Entry）。保留并改造原有的 `web/` (前端控制台)、`cli/` (命令行)、`mcp/` (大模型上下文协议) 等“壳”，将其全部对接到统一 of API 层，体现架构的“多端解耦”能力。

## 阶段四：售前包装与文档迁移
- [ ] TODO 7: 统一配置管理（整合相关的环境变量和配置解析，将原 MiniMax 客户端重构为通用 OpenAI 兼容客户端，以适配 Cloudflare Workers AI 等多模态 LLM 厂商）。
- [ ] TODO 8: 文档融合与重构。将两个项目的 `docs` 目录完整迁移到新项目，整合 API 文档、架构图，并针对融合后的系统修改八股文和从零教程。
- [ ] TODO 9: 撰写全新的 `README.md`，重点突显“企业级全场景知识闭环”的业务价值，作为简历上的核心抓手。
