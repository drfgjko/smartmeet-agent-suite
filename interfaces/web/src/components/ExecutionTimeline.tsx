import React, { useEffect, useRef } from "react";

type Event = {
  timestamp: number;
  message: string;
};

type ExecutionTimelineProps = {
  events: Event[];
  isLoading: boolean;
};

export default function ExecutionTimeline({ events, isLoading }: ExecutionTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="brutal-box p-0 bg-black overflow-hidden flex flex-col h-80 relative">
      {/* Terminal Header */}
      <div className="h-12 border-b-[3px] border-white flex items-center px-4 bg-[#ffc900] text-black shrink-0 z-10 relative">
        <div className="flex space-x-2 mr-4">
          <div className="w-3 h-3 border-[2px] border-black bg-white"></div>
          <div className="w-3 h-3 border-[2px] border-black bg-white"></div>
          <div className="w-3 h-3 border-[2px] border-black bg-white"></div>
        </div>
        <span className="font-black tracking-widest text-sm">AGENT 核心流转日志</span>
        {isLoading && (
          <div className="ml-auto w-3 h-3 bg-red-500 rounded-full animate-ping border-[2px] border-black"></div>
        )}
      </div>

      {/* Terminal Body */}
      <div 
        ref={containerRef}
        className="p-6 font-mono text-sm overflow-y-auto flex-1 bg-black text-[#4ade80]"
      >
        <div className="space-y-2">
          {events.map((ev, i) => (
            <div key={i} className="flex space-x-4">
              <span className="text-[#a1a1aa] shrink-0">
                [{new Date(ev.timestamp).toISOString().substring(11, 23)}]
              </span>
              <span className={`font-bold uppercase ${ev.message.includes("ERROR") || ev.message.includes("FAILED") ? "text-red-400" : "text-[#22d3ee]"}`}>
                {ev.message}
              </span>
            </div>
          ))}
          {isLoading && (
            <div className="flex space-x-4 animate-pulse">
              <span className="text-[#a1a1aa] shrink-0">
                [{new Date().toISOString().substring(11, 23)}]
              </span>
              <span className="font-bold uppercase text-[#ff90e8]">
                _
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
