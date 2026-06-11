"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode, useRef } from "react";

export type TaskStatus = "pending" | "processing" | "completed" | "error";

export interface Task {
  task_id: string;
  meeting_id: string;
  title: string;
  status: TaskStatus;
  message: string;
}

interface TaskContextType {
  tasks: Task[];
  addTask: (task_id: string, meeting_id: string, title: string) => void;
  removeTask: (task_id: string) => void;
  abortTask: (task_id: string) => void;
}

const TaskContext = createContext<TaskContextType | undefined>(undefined);

const API_BASE_WS =
  typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.hostname}:8000`
    : "ws://localhost:8000";

export function TaskProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const wsRefs = useRef<{ [key: string]: WebSocket }>({});

  const addTask = (task_id: string, meeting_id: string, title: string) => {
    setTasks((prev) => [
      ...prev,
      { task_id, meeting_id, title, status: "pending", message: "CONNECTING..." },
    ]);

    const ws = new WebSocket(`${API_BASE_WS}/ws/tasks/${meeting_id}/progress`);
    wsRefs.current[task_id] = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const stage = data.stage;

        setTasks((prev) =>
          prev.map((t) => {
            if (t.task_id === task_id) {
              if (stage === "done") {
                return { ...t, status: "completed", message: "COMPLETED" };
              } else if (stage === "error") {
                return { ...t, status: "error", message: data.message || "ERROR OCCURRED" };
              } else {
                return { ...t, status: "processing", message: data.message || `STAGE: ${stage.toUpperCase()}` };
              }
            }
            return t;
          })
        );

        if (stage === "done" || stage === "error") {
          ws.close();
        }
      } catch (e) {
        console.error("Task ws message parse error", e);
      }
    };

    ws.onerror = () => {
      setTasks((prev) =>
        prev.map((t) => (t.task_id === task_id ? { ...t, status: "error", message: "CONNECTION ERROR" } : t))
      );
    };
  };

  const removeTask = (task_id: string) => {
    setTasks((prev) => prev.filter((t) => t.task_id !== task_id));
    if (wsRefs.current[task_id]) {
      wsRefs.current[task_id].close();
      delete wsRefs.current[task_id];
    }
  };

  const abortTask = async (task_id: string) => {
    try {
      await fetch(`${API_BASE_WS.replace('ws://', 'http://').replace('wss://', 'https://')}/api/v1/tasks/${task_id}`, {
        method: "DELETE",
      });
      setTasks((prev) =>
        prev.map((t) =>
          t.task_id === task_id ? { ...t, status: "error", message: "ABORTED BY USER" } : t
        )
      );
      if (wsRefs.current[task_id]) {
        wsRefs.current[task_id].close();
        delete wsRefs.current[task_id];
      }
    } catch (e) {
      console.error("Failed to abort task", e);
    }
  };

  return (
    <TaskContext.Provider value={{ tasks, addTask, removeTask, abortTask }}>
      {children}
    </TaskContext.Provider>
  );
}

export function useTasks() {
  const context = useContext(TaskContext);
  if (!context) {
    throw new Error("useTasks must be used within a TaskProvider");
  }
  return context;
}
