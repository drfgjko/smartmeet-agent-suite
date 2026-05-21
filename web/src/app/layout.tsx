import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartMeet Agent Suite - 企业级多模态智能会议 Agent",
  description:
    "企业级多模态智能会议与全链路协同 Agent 解决方案。支持在线视频链接抓取、本地音视频上传、说话人分离、降噪增强，一键生成 PDF 讲义、思维导图与结构化会议纪要。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
        {children}
      </body>
    </html>
  );
}
