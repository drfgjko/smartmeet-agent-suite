# SmartMeet Agent Suite

SmartMeet Agent Suite 是一个结合多智能体工作流（LangGraph）与音视频处理引擎的开源工具。

该项目旨在将会议、销售录音、教程视频等复杂音视频流，自动化转化为结构化、高排版质量的 PDF 讲义、思维导图和待办清单。

## 项目背景

传统的长视频或长会议整理通常面临以下痛点：
1. **语音转文字缺乏结构**：纯文本转换结果通常为缺乏排版和重点的流水账。
2. **常规大模型总结单薄**：常规的单次摘要生成容易丢失决策细节及具体的任务分配（行动项）。
3. **产出物缺乏专业排版**：纯 Markdown 文本在部分企业级场景下显得不够正式。

本项目通过深度整合多智能体协作架构和底层音视频流解析，实现自动化直出企业级报告。

## 架构与工作流

本项目基于微服务化的事件驱动架构设计，核心工作流如下：

1. **媒体处理引擎（音视频解析）**
   支持本地音视频及 B站/YouTube 链接。底层采用 FFmpeg 进行降噪及音轨提取，结合 ASR (Whisper/FunASR) 进行语音转写，并通过 `pyannote-audio` 执行声纹分离。
   
2. **多智能体协作与语境感知（Agent 层）**
   核心基于 LangGraph 调度多个专职 Agent 进行流水线分析：
   - **Speaker Inference Agent**：基于对话上下文自动推断匿名发言人的真实身份并执行全局替换。
   - **Summary Agent**：提炼核心议题与结论。
   - **Action Agent**：精准提取行动项（人员、时间节点、任务）。
   - **Insight Agent**：分析情绪分布与发言效率。

3. **异步编排与持久化机制**
   - **状态机与任务队列**：内置基于 SQLite 的轻量级异步任务队列，支持后台执行长耗时计算任务与状态轮询。
   - **持久化 Checkpoint**：通过 `CheckpointService` 在提取、分析、渲染阶段自动保存 JSON 存档，支持断点续传与防崩溃兜底。

4. **排版与分发机制**
   排版层采用严格状态机的 LaTeX 模板注入 (Template Injection) 技术。结合 `Tectonic` 轻量级编译管线，输出带高亮边框和自动目录的 PDF 讲义。支持通过 Webhook 将结果自动推送至飞书群聊或 Jira 附件。

## 项目当前状态与多端说明

本项目采用“核心大底盘，全场景分发”的架构设计，支持多种交互端点，但**目前仅完成了核心后端 API 与 CLI 端的测试闭环**：

### 1. 交互端点状态
- ✅ **CLI 终端 (稳定可用)**：目前功能最稳定且经过完整测试的交互方式。核心流程与排版分发均推荐通过 CLI 或直接调用后端 API 体验。
- 🚧 **Web 端 (`web/`)**：前端代码处于初期占位阶段，尚未完成闭环测试。前端的 JobConfig 面板尚未适配后端结构化契约，暂不可用。
- 🚧 **MCP 协议端 (`mcp/`)**：早期版本代码，尚未适配最新 API 架构。
- 🚧 **桌面端 (`desktop/`)**：概念规划阶段。

### 2. 第三方平台集成状态
- ✅ **飞书 (Feishu)**：已完成全链路连通测试（含 Markdown 卡片推送拦截格式化、报告 PDF 附件上传）。
- 🚧 **Jira Cloud**：代码框架已就绪（`JiraClient` 及任务映射），但尚未在真实的 Jira 环境中进行鉴权和创建任务的闭环测试，使用时可能遇到环境或 Token 权限问题。
- 🚧 **通用 Webhook**：框架已预留，尚未实现具体业务逻辑。

## 部署与使用

本项目支持**混合算力架构**与**优雅降级**机制：若环境配置有 GPU 及相关环境，系统优先调用本地大模型和 Whisper；若处于轻量级环境，系统自动降级并切换至云端 API（如 OpenAI / Cloudflare Workers）。

### 部署方案选择

#### 方案 A：轻量级 Docker 部署 (适用云端算力)
适用于主要依赖云端 API（Cloud Whisper + Cloud LLM）的场景。可自行编写 Dockerfile 进行容器化部署。镜像仅需包含 Python 环境及 `FFmpeg`，无需配置 CUDA 及 PyTorch。

#### 方案 B：Miniconda 本地部署 (适用本地 GPU)
适用于需最大化利用本地 GPU 算力处理敏感数据的场景，推荐使用 Miniconda 实现环境隔离。

1. 安装 [Miniconda](https://docs.conda.io/en/latest/miniconda.html) (Python 3.11+)。
2. 在项目根目录执行以下命令创建包含 PyTorch、FFmpeg 等依赖的虚拟环境：
   ```bash
   conda env create -f environment.yml
   conda activate smartmeet
   ```

### 核心配置 (.env)

系统通过 `.env` 配置文件控制底层大模型和语音引擎的调度策略。

1. 复制配置模板：
   ```bash
   cp .env.example .env
   ```
2. **大语言模型 (LLM) 配置**：配置 `LLM_API_KEY` 和 `LLM_BASE_URL`，可对接 OpenAI、DeepSeek、Cloudflare 等兼容模型。
3. **语音引擎 (ASR) 调度**：通过 `ASR_ENGINE` 变量控制算力流向：
   - `ASR_ENGINE=auto` (默认)：优先探测并使用本地算力 (FunASR/Faster-Whisper)。
   - `ASR_ENGINE=openai` 或 `groq`：屏蔽本地模型，强制调用相应的云端 API 处理语音。

### 启动服务

**启动后端 API 服务：**
```bash
python -m api.main
```
启动成功后可置于后台运行。

**使用 CLI 客户端：**
在新的终端会话中（需处于激活的 conda 环境），可通过 CLI 处理音视频。

- **处理本地文件：**
  ```bash
  python -m cli process /path/to/your/audio.mp4 -c "Q3 预算评审会议"
  ```

- **处理在线视频：**
  ```bash
  python -m cli run "https://www.bilibili.com/video/BVxxxxx"
  ```

- **纯交付/分发处理 (Deliver)：**
  ```bash
  python -m cli.main deliver /path/to/final_result.json --sync-tasks
  ```
  *(注：完整 API 接口及集成指南详见 [docs/deployment-guide.md](docs/deployment-guide.md)。)*

## 系统与环境依赖

除 Python 依赖外，系统级组件要求如下：

1. **FFmpeg (必需)**
   - 核心用途：视频解析、音频抽取、降噪切片、关键帧提取。
   - 安装要求：Windows 需手动加入 `PATH`；Linux 推荐 `apt install ffmpeg`。
2. **Tectonic (LaTeX 核心排版引擎)**
   - 核心用途：负责高质量的 PDF 生成。项目根目录已自带便携版 `tectonic.exe`，您**不需要**在本地手动安装庞大的 LaTeX 发行版（如 TeX Live），程序运行期间引擎会自动通过网络拉取所需的轻量化宏包。
3. **GTK3 Runtime (针对 HTML 降级模式可选)**
   - 核心用途：当 LaTeX 编译失败触发 HTML 降级模式时，支撑 `WeasyPrint` 进行渲染。若未安装 GTK3，系统会最终兜底调用系统自带 Chrome/Edge 的无头模式（Headless）进行排版打印。
4. **CUDA 工具链 (可选)**
   - 核心用途：硬件加速 Whisper 及 pyannote 推理。

---

**开源鸣谢**：第三方开源组件声明详见 [CREDITS.txt](CREDITS.txt)。
