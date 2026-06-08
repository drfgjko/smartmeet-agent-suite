"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";

export default function Sidebar() {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
    const stored = localStorage.getItem("sidebar_collapsed");
    if (stored === "true") {
      setIsCollapsed(true);
    }
  }, []);

  const toggleCollapse = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("sidebar_collapsed", String(next));
      return next;
    });
  };

  const navItems = [
    { name: "工作台", icon: "WK", path: "/" },
    { name: "历史记录", icon: "HS", path: "/history" },
    { name: "系统设置", icon: "ST", path: "/settings" },
  ];

  return (
    <aside className={`${isCollapsed ? "w-20" : "w-64"} h-screen flex flex-col border-r-4 border-black bg-white flex-shrink-0 relative z-10 transition-all duration-300`}>
      {/* 顶部 Logo 区域 */}
      <div className="h-20 flex items-center justify-between px-4 border-b-4 border-black bg-[#ffc900] overflow-hidden">
        <div className="flex items-center">
          <div className="w-8 h-8 border-[3px] border-black bg-[#ff90e8] flex items-center justify-center shrink-0 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
            <span className="font-bold text-black leading-none mt-[-2px]">+</span>
          </div>
          {!isCollapsed && (
            <span className="font-black text-xl tracking-tight text-black uppercase ml-3 whitespace-nowrap">SmartMeet</span>
          )}
        </div>
      </div>
      
      {/* 侧边栏折叠按钮（悬浮在边界上） */}
      <button 
        onClick={toggleCollapse}
        className="absolute -right-4 top-6 w-8 h-8 bg-white border-[3px] border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] flex items-center justify-center font-black hover:bg-[#ffc900] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[1px_1px_0px_0px_rgba(0,0,0,1)] transition-all z-50"
      >
        {isCollapsed ? ">" : "<"}
      </button>

      {/* 导航菜单 */}
      <nav className="flex-1 py-8 px-3 space-y-4 overflow-y-auto overflow-x-hidden">
        {!isCollapsed && (
          <div className="text-sm font-black text-black tracking-widest mb-6 px-2 whitespace-nowrap">
            导航菜单
          </div>
        )}
        {navItems.map((item) => {
          const isActive = pathname === item.path || (item.path !== "/" && pathname.startsWith(item.path));
          return (
            <Link
              key={item.path}
              href={item.path}
              className={`flex items-center ${isCollapsed ? "justify-center px-0 py-3" : "px-4 py-3"} font-bold border-[3px] border-black transition-all duration-200 ${
                isActive 
                  ? "bg-[#22d3ee] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] translate-x-[-2px] translate-y-[-2px]" 
                  : "bg-white hover:bg-[#ff90e8] hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-2px] hover:translate-y-[-2px]"
              }`}
              title={isCollapsed ? item.name : ""}
            >
              {isCollapsed ? (
                <span className="text-black font-black">{item.icon}</span>
              ) : (
                <span className="text-black whitespace-nowrap">{item.name}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* 底部状态 */}
      <div className="p-4 border-t-4 border-black bg-[#f4f4f0]">
        <div className="border-[3px] border-black bg-white p-2 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] flex flex-col items-center justify-center">
          {isCollapsed ? (
            <div className={`w-4 h-4 border-2 border-black ${process.env.NEXT_PUBLIC_DEMO_MODE === "true" ? "bg-[#ffc900]" : "bg-[#4ade80]"}`}></div>
          ) : (
            <>
              <div className="flex items-center w-full">
                <div className={`w-3 h-3 border-2 border-black mr-2 shrink-0 ${process.env.NEXT_PUBLIC_DEMO_MODE === "true" ? "bg-[#ffc900]" : "bg-[#4ade80]"}`}></div>
                <span className="text-sm font-bold text-black truncate">{process.env.NEXT_PUBLIC_DEMO_MODE === "true" ? "静态演示" : "运行中"}</span>
              </div>
              <div className={`mt-2 text-[10px] font-black tracking-wider border-t-2 border-black pt-2 w-full truncate ${process.env.NEXT_PUBLIC_DEMO_MODE === "true" ? "text-[#ffc900] bg-black px-1 uppercase" : "text-gray-600"}`}>
                {process.env.NEXT_PUBLIC_DEMO_MODE === "true" ? "VERCEL ENV" : "本地网络"}
              </div>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
