# Agent 协作规范与约束 (AGENTS.md)

本文档旨在约束本项目中所有 AI 助手（包括但不限于 Cursor、Agentic 工作流等）的行为准则、代码规范与提交流程。
回答时使用中文。
必须使用中文注释。

## 一、第一性原理与核心原则
1. 审慎思考：从原始需求和问题出发。如果动机和目标不清晰，停下来与用户讨论。
2. 最短路径：最简路径实现，绝对不允许过度设计。
3. 无缝执行与拒绝静默失败：不做针对“脏代码/历史包袱”的折中兼容，不加无实际需求的防御性兜底。系统内部调用应优先 fail-fast 暴露问题。若因外部环境等不可控因素必须进行优雅降级，必须伴随显式日志（Warning/Error级别）和可追溯的状态标记，严禁任何形式的静默失败。
4. 验证闭环：必须确保方案逻辑正确，经过全链路验证，fail-fast。
5. 耦合自省：在编写或重构任何代码时，必须时刻反问自己：耦合少、耦合显式、耦合可测试吗？以保证单模块的高独立性。

## 二、代码开发规范
1. 操作确认：处理任务时必须先列出 TODO 列表，得到用户确认后方可进行代码操作（用户未要求修改代码时，默认为讨论）。
2. 终端指令：如需使用终端指令，只可以使用 cmd，不要使用 powershell。如果指令执行报错，考虑使用 cmd.exe /c。
3. 编码“死命令”：为了彻底杜绝乱码及 Emoji 导致的崩溃，必须严格遵守以下三条编码底线：
   - 所有的 open() 操作必须显式指定 encoding='utf-8'。
   - 所有返回中文字符串的 json.dumps() 必须指定 ensure_ascii=False。
   - 配置环境时需在 .env 中声明 PYTHONIOENCODING=utf-8。
4. 模块边界约束：
   - services 层的子模块之间禁止直接导入下划线前缀的私有函数，必须通过 __init__.py 暴露的公开 API 调用。
   - agents 层的每个 Agent 的输入输出必须符合 schemas/ 中定义的契约模型，禁止使用裸 dict 传递结构化数据。
5. LLM 客户端注入与统一规范：所有需要调用 LLM 的模块必须通过构造函数注入由 services.integrations.llm_client.create_llm_client() 产生的统一客户端，禁止在模块内部直接实例化 OpenAI() 或使用废弃的特定厂商客户端（如原 MiniMaxClient）。

## 三、Git 提交规范
所有代码修改的 Commit Message 必须遵循以下结构化格式（参考 Conventional Commits）：

防吞空行硬性工作流 (Windows/Git Bash 环境保护)：
为了防止多行文本和换行符在终端中粘贴时丢失格式，以及确保提交信息完整，所有长篇幅提交必须遵循以下自动化流程：
1. 检测全局未提交状态：在生成 commit_msg.txt 前，AI 必须运行 git status 审查当前工作区内所有尚未 commit 的修改（包括修改、新增、删除的文件），汇总全部未提交文件的变更内容，确保提交信息的完整性，绝不允许只记录最近一次对话的局部修改。
2. 由 AI 生成一个临时的 commit_msg.txt 文件存放上述汇总的完整格式文本。
3. 提示用户（或由 AI）执行：git commit -F commit_msg.txt (若为修改则加 --amend)。
4. 提交成功后立刻删除该临时文件 rm commit_msg.txt。
5. 禁用 Markdown 加粗：生成的 commit_msg.txt 第一行（即 <type>: <标题> 这一行）必须是纯文本，绝对禁止使用任何加粗标记（如 **）或其他 Markdown 格式。
6. 提交说明使用中文：除了 <type> 前缀（如 feat:, fix: 等）外，标题、正文的所有变更描述必须统一使用中文。
7. 拒绝流水账描述：生成的提交说明必须聚焦于架构、功能及逻辑层面的核心演进，绝对禁止在描述中罗列如“修改文档”、“注释翻译/汉化”、“清理无用临时文件/gitkeep”等琐碎的日常维护和辅助操作。

标准模板参考：
```text
<type>: <标题>

新增功能/架构更新：
- <具体变更点1>
- <具体变更点2>
- 拆分 FollowUp 闭环能力，引入 reporting 与 delivery 服务承接报告组装、渲染、脑图生成和多渠道分发

修复/工程化更新：
- <具体修复或优化项>

Made-with: Gemini 3.1 Pro
```
注：<type> 可选值为 feat, fix, chore, refactor, docs 等。

## 四、项目架构与环境约束
1. 项目名称：smartmeet-agent-suite (企业级多模态智能会议与全链路协同 Agent 解决方案)
2. 环境基底：推崇基于 Miniconda 的环境管理，以固化底层科学计算库（PyTorch）和媒体处理库（FFmpeg）。执行测试、启动服务或运行脚本时，必须在对应的 miniconda 虚拟环境中进行（例如使用 `conda run -n smartmeet python -m pytest ...`），以防止因全局环境缺少依赖而运行失败。
3. 受限优雅降级：优雅降级设计仅限大模型等外部基础设施失效，或本地重型计算库（如 GPU 依赖）缺失的基建层硬件失效场景。降级发生时，必须向上层显式报告“降级状态”或抛出特定异常，禁止掩盖真实错误。默认倾向使用成本优化方案（如 Cloudflare Workers AI 提供的 Serverless 模型）。
4. 模块依赖方向约束：
   - agents -> services 为合法依赖方向。
   - services 子模块之间的依赖必须通过各自的 __init__.py 门面进行。
   - document_engine 不得下钻到 media_engine 的内部模块。
5. Schema-First 原则：当 Agent 间需要传递结构化数据时，必须先在 schemas/ 目录定义 Pydantic 模型，再编写实现代码。
