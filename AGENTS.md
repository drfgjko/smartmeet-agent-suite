# Agent 协作规范与约束 (AGENTS.md)

本文档旨在约束本项目中所有 AI 助手（包括但不限于 Cursor、Agentic 工作流等）的行为准则、代码规范与提交流程。

## 一、第一性原理与核心原则
1. **审慎思考**：从原始需求和问题出发。如果动机和目标不清晰，停下来与用户讨论。
2. **最短路径**：最简路径实现，**绝对不允许过度设计**。
3. **无缝执行**：不允许给出兼容性或补丁性的方案，不做回退式兼容，不加无需求兜底。
4. **验证闭环**：必须确保方案逻辑正确，经过全链路验证，fail-fast。

## 二、代码开发规范
1. **操作确认**：处理任务时必须先列出 TODO 列表，得到用户确认后方可进行代码操作（用户未要求修改代码时，默认为讨论）。
2. **终端指令**：如需使用终端指令，**只可以使用 cmd**，不要使用 powershell。如果指令执行报错，考虑使用 `cmd.exe /c`。
3. **编码“死命令”**：为了彻底杜绝乱码及 Emoji 导致的崩溃，必须严格遵守以下三条编码底线：
   - 所有的 `open()` 操作必须显式指定 `encoding='utf-8'`。
   - 所有返回中文字符串的 `json.dumps()` 必须指定 `ensure_ascii=False`。
   - 配置环境时需在 `.env` 中声明 `PYTHONIOENCODING=utf-8`。

## 三、Git 提交规范
所有代码修改的 Commit Message 必须遵循以下结构化格式（参考 Conventional Commits）：

**防吞空行硬性工作流 (Windows/Git Bash 环境保护)：**
为了防止多行文本和换行符在终端中粘贴时丢失格式，所有长篇幅提交必须遵循以下自动化流程：
1. 由 AI 生成一个临时的 `commit_msg.txt` 文件存放标准格式文本。
2. 提示用户（或由 AI）执行：`git commit -F commit_msg.txt` (若为修改则加 `--amend`)。
3. 提交成功后立刻删除该临时文件 `rm commit_msg.txt`。

**标准模板参考：**
```text
<type>: <标题>

新增功能/架构更新：
- <具体变更点1>
- <具体变更点2>

修复/工程化更新：
- <具体修复或优化项>

Made-with: Gemini 3.1 Pro
```
*注：`<type>` 可选值为 `feat`, `fix`, `chore`, `refactor`, `docs` 等。*

## 四、项目架构与环境约束
1. **项目名称**：`smartmeet-agent-suite` (企业级多模态智能会议与全链路协同 Agent 解决方案)
2. **环境基底**：推崇基于 Miniconda 的环境管理，以固化底层科学计算库（PyTorch）和媒体处理库（FFmpeg）。
3. **优雅降级**：大模型及第三方服务接入推崇 Graceful Degradation 设计。默认倾向使用成本优化方案（如 Cloudflare Workers AI 提供的 Serverless 模型）。
