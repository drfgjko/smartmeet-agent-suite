import type { Metadata } from "next";
import Sidebar from "@/components/layout/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartMeet Agent Suite - 会议协同 Agent",
  description:
    "企业级多模态智能会议与全链路协同 Agent 解决方案。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen flex bg-[#f4f4f0] text-black overflow-hidden font-sans selection:bg-[#ff90e8] selection:text-black">
        <Sidebar />
        <main className="flex-1 flex flex-col h-screen overflow-y-auto">
          {children}
        </main>
      </body>
    </html>
  );
}
