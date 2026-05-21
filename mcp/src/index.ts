#!/usr/bin/env node
/**
 * SmartMeet MCP 服务端实现
 *
 * 为外部大模型提供音视频/会议记录转化为结构化会议报告的 Tool 工具。
 * 底层调用统一的 FastAPI 服务（默认端口 8000），由 4 个 AI Agent 并行协作：
 * 摘要提取、行动项提取、发言洞察分析、报告组装与分发。
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "smartmeet",
  version: "2.0.0",
});

/**
 * 通用的 FastAPI 处理接口调用辅助函数
 */
async function callProcessAPI(params: URLSearchParams): Promise<any> {
  const apiBase = process.env.SMARTMEET_API || "http://127.0.0.1:8000";
  const resp = await fetch(`${apiBase}/api/v1/recording/process`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params,
  });
  if (!resp.ok) {
    const errorText = await resp.text();
    throw new Error(`HTTP ${resp.status} - ${errorText}`);
  }
  return await resp.json();
}

// ---------- 工具 (Tools) 定义 ----------

server.tool(
  "summarize_video",
  "将 B站/YouTube 等在线视频链接转换为结构化会议报告，包含摘要、行动项、发言洞察，并可生成为 PDF",
  {
    url: z.string().describe("在线视频链接地址"),
    context: z.string().optional().describe("补充上下文背景信息，帮助 AI 更准确理解内容"),
  },
  async ({ url, context }) => {
    const params = new URLSearchParams();
    params.append("url", url);
    if (context) {
      params.append("context", context);
    }
    try {
      const data = await callProcessAPI(params);
      return {
        content: [{
          type: "text" as const,
          text: `# ${data.title || "视频会议报告"}\n\n${data.content || "未生成任何内容。"}`
        }],
      };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `错误信息: ${err.message}` }] };
    }
  }
);

server.tool(
  "process_recording",
  "处理本地音视频文件，经降噪、说话人分离后由 4 个 AI Agent 并行生成：结构化摘要、行动项、发言洞察与 PDF 报告",
  {
    file_path: z.string().describe("宿主机上的本地音视频文件绝对路径"),
    context: z.string().optional().describe("会议/录制内容描述（如：AI开源圆桌讨论会）"),
    num_speakers: z.number().optional().describe("发言人数量（若不传则系统自动检测）"),
    denoise_level: z.number().min(0).max(3).default(1).describe("降噪强度等级 (0=无, 1=轻度, 2=中度, 3=重度)"),
  },
  async ({ file_path, context, num_speakers, denoise_level }) => {
    const params = new URLSearchParams();
    params.append("file_path", file_path);
    if (context) params.append("context", context);
    if (num_speakers !== undefined) params.append("num_speakers", String(num_speakers));
    params.append("denoise_level", String(denoise_level));
    try {
      const data = await callProcessAPI(params);
      return {
        content: [{
          type: "text" as const,
          text: `# ${data.title || "会议报告"}\n\n${data.content || "未生成任何内容。"}`
        }],
      };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `错误信息: ${err.message}` }] };
    }
  }
);

server.tool(
  "get_transcript",
  "提取在线视频或本地音视频文件的语音识别（ASR）转录文本",
  {
    url: z.string().optional().describe("在线视频链接地址"),
    file_path: z.string().optional().describe("本地音视频文件的绝对路径")
  },
  async ({ url, file_path }) => {
    if (!url && !file_path) {
      return { content: [{ type: "text" as const, text: "错误: 必须提供 url 或 file_path 中的至少一个。" }] };
    }
    const params = new URLSearchParams();
    if (url) params.append("url", url);
    if (file_path) params.append("file_path", file_path);
    params.append("extract_frames", "false");
    try {
      const data = await callProcessAPI(params);
      return {
        content: [{
          type: "text" as const,
          text: data.diarized_transcript || data.transcript || "未找到任何转录文本。"
        }],
      };
    } catch (err: any) {
      return { content: [{ type: "text" as const, text: `错误信息: ${err.message}` }] };
    }
  }
);

server.tool(
  "list_capabilities",
  "列出 SmartMeet 系统实际提供的处理能力与输出格式",
  {},
  async () => {
    return {
      content: [{
        type: "text" as const,
        text: `# SmartMeet 系统能力

## 输入方式
- **在线链接**: B站、YouTube 等视频链接（通过 URL 抓取）
- **本地文件**: 支持 MP4/MP3/WAV/M4A/WebM 等格式

## 处理流程（4 个 AI Agent 并行）
1. **摘要提取**: 提炼议题、讨论要点、决策结论
2. **行动项提取**: 识别"谁、何时、做什么"并同步至 Jira/飞书
3. **发言洞察**: 发言时长统计、情绪分析、会议效率评分
4. **报告组装**: 渲染 Markdown/PDF/HTML/思维导图，并分发至飞书/Jira

## 输出格式
- **Markdown**: 结构化会议纪要
- **PDF**: LaTeX 渲染的专业讲义（含关键帧截图）
- **HTML**: 网页版报告
- **思维导图**: Mermaid 格式脑图

## 处理参数
- \`num_speakers\`: 手动指定发言人数（默认自动检测）
- \`denoise_level\`: 降噪强度 (0=关闭, 1=轻度, 2=中度, 3=强力)
- \`context\`: 补充背景上下文，帮助 AI 更准确理解会议内容`,
      }],
    };
  }
);

// ---------- Start ----------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("SmartMeet MCP Server running on STDIO");
}

main().catch(console.error);
