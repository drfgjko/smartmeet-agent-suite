"use client";

import { useRouter } from "next/navigation";
import { Result } from "../types";
import UploadPanel from "../components/UploadPanel";

const API_BASE =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://api:8000";

export default function Home() {
  const router = useRouter();

  const handleUploadSuccess = (r: Result) => {
    // Navigate to the result page instead of updating state locally
    router.push(`/result?meeting_id=${r.meeting_id}`);
  };

  return (
    <div className="w-full h-full flex flex-col">
      <div className="p-8 max-w-5xl mx-auto w-full relative">
        <div className="mb-12 border-b-[4px] border-black pb-6 flex items-end justify-between">
          <div>
            <h1 className="text-6xl font-black tracking-tighter">工作台</h1>
            <p className="font-bold text-gray-700 mt-2 text-xl">SMARTMEET</p>
          </div>
          {/* 仅开发环境：快速加载 Mock 数据跳过流水线，用于 UI 调试 */}
          {process.env.NODE_ENV === "development" && (
            <button
              id="dev-load-mock-btn"
              onClick={() => router.push("/result?meeting_id=mock-37fe9e7b")}
              className="brutal-btn text-xs bg-[#ffc900] hover:shadow-[6px_6px_0px_rgba(0,0,0,1)] border-dashed"
              title="开发模式：跳过流水线，直接载入 Mock 结果预览布局"
            >
              [DEV] 加载 Mock 数据
            </button>
          )}
        </div>
        <UploadPanel API_BASE={API_BASE} onSuccess={handleUploadSuccess} />
      </div>
    </div>
  );
}
