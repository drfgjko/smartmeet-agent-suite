"use client";

import { useState } from "react";
import { Result } from "../types";
import UploadPanel from "../components/UploadPanel";

const API_BASE =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://api:8000";

export default function Home() {
  const [result, setResult] = useState<Result | null>(null);

  const handleUploadSuccess = (r: Result, input: string) => {
    setResult(r);
  };

  return (
    <div className="p-8 max-w-5xl mx-auto w-full">
      <div className="mb-12 border-b-[4px] border-black pb-6">
        <h1 className="text-6xl font-black tracking-tighter">工作台</h1>
        <p className="font-bold text-gray-700 mt-2 text-xl">SMARTMEET 智能中枢</p>
      </div>

      {!result ? (
        <UploadPanel 
          API_BASE={API_BASE} 
          onSuccess={handleUploadSuccess} 
        />
      ) : (
        <div className="brutal-box p-8 bg-[#4ade80]">
          <h2 className="text-4xl font-black mb-4">分析已完成</h2>
          <p className="font-bold mb-6 text-xl">分析结果面板（阶段四）正在加紧施工中。</p>
          <button 
            onClick={() => setResult(null)}
            className="brutal-btn bg-white"
          >
            开启新任务
          </button>
        </div>
      )}
    </div>
  );
}
