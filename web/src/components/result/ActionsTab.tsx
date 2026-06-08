import React from "react";

type ActionItem = {
  task: string;
  assignee?: string;
  deadline?: string;
  priority?: string;
  context?: string;
  feishu_task_id?: string;
  jira_issue_key?: string;
};

type ActionsData = {
  action_items?: ActionItem[];
};

type ActionsTabProps = {
  actions: ActionsData;
};

/** 优先级 → 配色 */
function priorityStyle(priority?: string): { bg: string; label: string } {
  switch ((priority ?? "").toLowerCase()) {
    case "high":
    case "urgent":
    case "紧急":
    case "高":
      return { bg: "#f87171", label: "高" };
    case "low":
    case "低":
      return { bg: "#d1d5db", label: "低" };
    default:
      return { bg: "#ffc900", label: "中" };
  }
}

export default function ActionsTab({ actions }: ActionsTabProps) {
  const items = actions?.action_items ?? [];

  if (items.length === 0) {
    return (
      <p className="text-xs font-bold text-gray-400 text-center py-12">
        暂无待办事项
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-black text-gray-400 uppercase tracking-widest">
        共 {items.length} 项待办
      </p>

      {items.map((item, i) => {
        const { bg, label } = priorityStyle(item.priority);
        const hasSynced = item.feishu_task_id || item.jira_issue_key;

        return (
          <div
            key={i}
            id={`action-item-${i}`}
            className="brutal-box p-4 bg-white flex flex-col gap-2"
          >
            {/* 顶部：负责人 + 优先级标签 */}
            <div className="flex items-center justify-between">
              <span className="text-xs font-black px-2 py-0.5 border-[2px] border-black bg-[#f4f4f0] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
                {item.assignee || "未指定"}
              </span>
              <span
                className="text-xs font-black px-2 py-0.5 border-[2px] border-black shadow-[2px_2px_0px_rgba(0,0,0,1)]"
                style={{ backgroundColor: bg }}
              >
                {label}
              </span>
            </div>

            {/* 任务内容 */}
            <p className="text-sm font-bold leading-snug">{item.task}</p>

            {/* 上下文（可选） */}
            {item.context && (
              <p className="text-xs text-gray-500 leading-relaxed">{item.context}</p>
            )}

            {/* 底部：截止日期 + 同步状态 */}
            <div className="flex items-center justify-between pt-2 border-t-[1.5px] border-black/10 mt-1">
              <span className="text-xs font-bold text-gray-500">
                截止：{item.deadline || "无期限"}
              </span>
              {hasSynced && (
                <div className="flex gap-1.5">
                  {item.feishu_task_id && (
                    <span className="text-[10px] font-black px-1.5 py-0.5 bg-[#4ade80] border-[1.5px] border-black">
                      飞书
                    </span>
                  )}
                  {item.jira_issue_key && (
                    <span className="text-[10px] font-black px-1.5 py-0.5 bg-[#22d3ee] border-[1.5px] border-black">
                      {item.jira_issue_key}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
