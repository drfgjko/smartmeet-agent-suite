# SmartMeet

本项目是一条基于大模型和强数据契约的确定性自动化流水线。支持音视频输入，自动提取核心议题、精准待办、情绪洞察，并生成带关键帧的 LaTeX PDF 报告与思维导图，最终支持分钟级推送到飞书群聊。

## 架构与工作流

本项目采用本地单体架构，通过轻量级异步任务队列实现模块解耦，核心工作流如下：

1. **媒体处理引擎（音视频解析）**
   支持本地音视频及 B站/YouTube 链接。底层采用 FFmpeg 进行降噪及音轨提取，结合 ASR (Whisper/FunASR) 进行语音转写，并通过 `pyannote-audio` 执行声纹分离。
   
2. **大模型流水线核心层（Node 层）**
   核心基于 LangGraph 调度多个专职处理节点进行并行流水线分析：
   - **Speaker Inference 节点**：基于对话上下文自动推断匿名发言人的真实身份并执行全局替换。
   - **Summary 节点**：提炼核心议题与结论。
   - **Action 节点**：精准提取行动项（人员、时间节点、任务）。
   - **Insight 节点**：分析情绪分布与发言效率。

3. **异步编排与持久化机制**
   - **状态机与任务队列**：引入 Arq 与 Redis 构建核心异步任务队列驱动，提供独立的 Worker 进程解耦并承载长耗时音视频处理任务，前端提供全局任务状态中心进行轮询监控。
   - **持久化 Checkpoint**：通过 `CheckpointService` 在提取、分析、渲染阶段自动保存 JSON 存档，支持断点续传与防崩溃兜底。

4. **排版与分发机制**
   排版层采用严格状态机的 LaTeX 模板注入 (Template Injection) 技术。结合 `Tectonic` 轻量级编译管线，输出带高亮边框和自动目录的 PDF 讲义。支持通过飞书自建应用 (Open API) 将包含 PDF/思维导图等实体附件的会议结果自动推送至飞书群聊。

5. **配置与资产管理**
   内置系统配置管理（集成状态探测）及独立的历史报告服务器。原生提供音频流获取能力，支持从 Web 或第三方客户端对已完成的会议产物（Markdown、PDF、HTML、思维导图等）进行回看与删除。

## 系统与环境依赖

除 Python 依赖外，系统级组件要求如下：

1. **FFmpeg (必需)**
   - 核心用途：视频解析、音频抽取、降噪切片、关键帧提取。
   - 安装要求：Windows 需手动加入 PATH；Linux 推荐 `apt install ffmpeg`。
2. **Tectonic (LaTeX 核心排版引擎)**
   - 核心用途：负责高质量的 PDF 生成。项目根目录已自带便携版 `tectonic.exe`，您**不需要**在本地手动安装庞大的 LaTeX 发行版（如 TeX Live），程序运行期间引擎会自动通过网络拉取所需的轻量化宏包。
3. **GTK3 Runtime (针对 HTML 降级模式可选)**
   - 核心用途：当 LaTeX 编译失败触发 HTML 降级模式时，支撑 `WeasyPrint` 进行渲染。若未安装 GTK3，系统会最终兜底调用系统自带 Chrome/Edge 的无头模式（Headless）进行排版打印。
4. **CUDA 工具链 (可选)**
   - 核心用途：硬件加速 Whisper 及 pyannote 推理。
5. **Redis 6.0+ (必需)**
   - 核心用途：提供 Arq 异步任务队列的存储底座，支撑长耗时后台任务。
6. **Miniconda (推荐)**
   - 核心用途：用于底层科学计算库和环境依赖隔离。

## 快速部署

```bash
git clone https://github.com/your-username/smartmeet-agent-suite.git
cd smartmeet-agent-suite

# 创建虚拟环境并安装后端依赖
conda env create -f environment.yml
conda activate smartmeet

# 安装前端依赖
cd frontend
npm install
cd ..

# 复制并填写配置文件 (配置 LLM_API_KEY)
cp .env.example .env
```

## 启动服务

**方法一：Web 工作台（多进程协同启动）**
- Windows: 双击 `start.bat`
- macOS / Linux: 运行 `conda run -n smartmeet python start_launcher.py`
启动后访问 http://localhost:3000

**方法二：CLI 命令行执行**
```bash
# 处理本地文件
conda run -n smartmeet python -m cli process /path/to/video.mp4 -c "Q3预算评审"

# 处理在线视频
conda run -n smartmeet python -m cli run "https://www.bilibili.com/video/BVxxxxx"
```
更多 CLI 接口及集成说明详见 [docs/deployment-guide.md](docs/deployment-guide.md)。

## 鸣谢

本项目初期参考了 [multi-agent-meeting-assistant](https://github.com/bcefghj/multi-agent-meeting-assistant) 项目。该项目包装为“Multi-Agent”，但代码本质是将固定 LLM 调用串联的自动化流水线（Pipeline），并不具备多智能体的自主规划能力。警惕过度包装。

第三方组件声明详见 [CREDITS.txt](CREDITS.txt)。
