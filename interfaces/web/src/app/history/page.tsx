"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://api:8000";

type ReportInfo = {
  meeting_id: string;
  title: string;
  status: string;
  duration: number;
  num_speakers: number;
  created_at: number;
};

function formatDuration(secs: number) {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatDate(ts: number) {
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function HistoryPage() {
  const [reports, setReports] = useState<ReportInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const fetchReports = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/reports`);
      const data = await res.json();
      setReports(data);
    } catch (err) {
      console.error("Failed to fetch reports:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleDelete = async (e: React.MouseEvent, meetingId: string) => {
    e.stopPropagation(); // 防止触发卡片点击跳转
    if (!confirm("确认彻底删除该会议的所有产物记录吗？此操作不可逆！")) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/reports/${meetingId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setReports((prev) => prev.filter((r) => r.meeting_id !== meetingId));
      } else {
        alert("删除失败，请稍后重试");
      }
    } catch (err) {
      console.error("Delete failed:", err);
      alert("删除失败，请检查网络连接");
    }
  };

  const handleCardClick = (meetingId: string, status: string) => {
    if (status !== "COMPLETED") {
      alert("该任务仍在处理中或已损坏，无法查看。");
      return;
    }
    // 携带参数跳转至主页加载结果
    router.push(`/?meeting_id=${meetingId}`);
  };

  return (
    <div className="w-full h-full flex flex-col bg-[#f4f4f0]">
      {/* 顶部 Header */}
      <div className="flex-shrink-0 p-8 border-b-[4px] border-black bg-white">
        <h1 className="text-5xl font-black tracking-tighter">历史记录</h1>
        <p className="font-bold text-gray-500 mt-3 text-sm">
          查看以往的会议分析产物
        </p>
      </div>

      {/* 主体列表 */}
      <div className="flex-1 overflow-y-auto p-8">
        {loading ? (
          <div className="text-center font-bold text-gray-400 mt-20 text-xl">
            加载中...
          </div>
        ) : reports.length === 0 ? (
          <div className="text-center mt-32">
            <span className="text-6xl mb-4 inline-block">📭</span>
            <p className="font-black text-2xl text-gray-400">暂无历史记录</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {reports.map((report) => {
              const isCompleted = report.status === "COMPLETED";

              return (
                <div
                  key={report.meeting_id}
                  onClick={() => handleCardClick(report.meeting_id, report.status)}
                  className={`brutal-box p-5 flex flex-col bg-white relative group transition-all duration-200 ${
                    isCompleted
                      ? "cursor-pointer hover:-translate-y-1 hover:translate-x-1 hover:shadow-[8px_8px_0px_rgba(0,0,0,1)]"
                      : "opacity-60 grayscale cursor-not-allowed"
                  }`}
                >
                  {/* 状态徽章 */}
                  <div className="flex justify-between items-start mb-4">
                    <span
                      className={`text-[10px] font-black px-2 py-0.5 border-[2px] border-black shadow-[2px_2px_0px_rgba(0,0,0,1)] ${
                        isCompleted ? "bg-[#4ade80]" : "bg-[#ffc900]"
                      }`}
                    >
                      {report.status}
                    </span>
                    {/* 删除按钮 */}
                    <button
                      onClick={(e) => handleDelete(e, report.meeting_id)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity w-6 h-6 border-[2px] border-black bg-[#f87171] text-white flex items-center justify-center font-black text-xs hover:bg-red-600 shadow-[2px_2px_0px_rgba(0,0,0,1)]"
                      title="删除记录"
                    >
                      ✕
                    </button>
                  </div>

                  {/* 标题 */}
                  <h3 className="font-black text-lg leading-tight mb-2 line-clamp-2">
                    {report.title}
                  </h3>

                  {/* ID */}
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4">
                    ID: {report.meeting_id}
                  </p>

                  <div className="mt-auto space-y-2 border-t-[2px] border-black/10 pt-4">
                    {/* 基础统计 */}
                    <div className="flex items-center justify-between text-xs font-bold text-gray-600">
                      <span>时长: {formatDuration(report.duration)}</span>
                      <span>发言人: {report.num_speakers}</span>
                    </div>
                    {/* 时间 */}
                    <div className="text-[10px] font-bold text-gray-400 text-right">
                      {formatDate(report.created_at)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
