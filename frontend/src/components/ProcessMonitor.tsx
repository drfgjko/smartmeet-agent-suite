"use client";

import React from "react";
import { useTasks } from "./TaskProvider";
import { useRouter } from "next/navigation";

export default function ProcessMonitor() {
  const { tasks, removeTask, abortTask } = useTasks();
  const router = useRouter();

  if (tasks.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-4 max-w-sm w-full pointer-events-none">
      {tasks.map((task) => (
        <div
          key={task.task_id}
          className="brutal-box flex flex-col pointer-events-auto overflow-hidden bg-white"
        >
          <div className="bg-[#ff90e8] text-black px-4 py-3 flex justify-between items-center border-b-[3px] border-black">
            <span className="font-black text-xs tracking-wider uppercase">
              Process Monitor
            </span>
            <button
              onClick={() => removeTask(task.task_id)}
              className="text-black hover:scale-110 font-black text-lg transition-transform"
              title="Dismiss"
            >
              ✕
            </button>
          </div>

          <div className="p-4 flex flex-col gap-3 bg-white">
            <div className="font-black text-sm text-black truncate" title={task.title}>
              {task.title}
            </div>
            
            <div className="flex items-center gap-2 font-bold">
              <span className={`w-3 h-3 border-[2px] border-black rounded-full ${
                task.status === 'completed' ? 'bg-[#4ade80]' : 
                task.status === 'error' ? 'bg-[#f87171]' : 'bg-[#22d3ee] animate-pulse'
              }`}></span>
              <span className="text-xs text-black uppercase tracking-wide">
                {task.status}
              </span>
            </div>

            <div className="text-xs text-black font-medium break-words line-clamp-2">
              {task.message}
            </div>


            {task.status === "completed" && (
              <button
                onClick={() => router.push(`/result?meeting_id=${task.meeting_id}`)}
                className="mt-2 brutal-btn w-full bg-[#ffc900] py-2 text-sm uppercase"
              >
                View Report
              </button>
            )}
            
            {(task.status === "pending" || task.status === "processing") && (
              <button
                onClick={() => abortTask(task.task_id)}
                className="mt-2 brutal-btn w-full bg-[#f87171] py-2 text-sm uppercase"
              >
                Abort Task
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
