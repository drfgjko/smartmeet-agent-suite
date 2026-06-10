"use client";

import React from "react";
import { useTasks } from "./TaskProvider";
import { useRouter } from "next/navigation";

export default function ProcessMonitor() {
  const { tasks, removeTask, abortTask } = useTasks();
  const router = useRouter();

  if (tasks.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none">
      {tasks.map((task) => (
        <div
          key={task.task_id}
          className="bg-white border border-gray-200 shadow-lg rounded-md flex flex-col pointer-events-auto overflow-hidden"
        >
          <div className="bg-gray-50 text-gray-800 px-4 py-3 flex justify-between items-center border-b border-gray-100">
            <span className="font-semibold text-xs tracking-wider uppercase text-gray-500">
              Process Monitor
            </span>
            <button
              onClick={() => removeTask(task.task_id)}
              className="text-gray-400 hover:text-gray-800 font-bold text-sm transition-colors"
              title="Dismiss"
            >
              ✕
            </button>
          </div>

          <div className="p-4 flex flex-col gap-3">
            <div className="font-medium text-sm text-gray-900 truncate" title={task.title}>
              {task.title}
            </div>
            
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${
                task.status === 'completed' ? 'bg-green-500' : 
                task.status === 'error' ? 'bg-red-500' : 'bg-blue-500 animate-pulse'
              }`}></span>
              <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">
                {task.status}
              </span>
            </div>

            <div className="text-xs text-gray-500 break-words line-clamp-2">
              {task.message}
            </div>


            {task.status === "completed" && (
              <button
                onClick={() => router.push(`/result?meeting_id=${task.meeting_id}`)}
                className="mt-2 w-full bg-black text-white hover:bg-gray-800 py-2 rounded text-sm font-medium transition-colors"
              >
                View Report
              </button>
            )}
            
            {(task.status === "pending" || task.status === "processing") && (
              <button
                onClick={() => abortTask(task.task_id)}
                className="mt-2 w-full bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 py-2 rounded text-sm font-medium transition-colors"
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
