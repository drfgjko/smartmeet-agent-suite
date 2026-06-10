import type { Metadata } from "next";
import Sidebar from "@/components/layout/Sidebar";
import { TaskProvider } from "@/components/TaskProvider";
import ProcessMonitor from "@/components/ProcessMonitor";
import "./globals.css";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen flex bg-[#f4f4f0] text-black overflow-hidden font-sans selection:bg-[#ff90e8] selection:text-black">
        <TaskProvider>
          <Sidebar />
          <main className="flex-1 flex flex-col h-screen overflow-y-auto">
            {children}
          </main>
          <ProcessMonitor />
        </TaskProvider>
      </body>
    </html>
  );
}
