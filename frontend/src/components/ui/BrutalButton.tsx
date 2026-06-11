import React from "react";

export type BrutalButtonProps = {
  id?: string;
  children: React.ReactNode;
  onClick?: () => void;
  href?: string;
  disabled?: boolean;
  accent?: string;
  className?: string;
  type?: "button" | "submit" | "reset";
  size?: "sm" | "md" | "lg";
};

export default function BrutalButton({
  id,
  children,
  onClick,
  href,
  disabled,
  accent,
  className = "",
  type = "button",
  size = "md",
}: BrutalButtonProps) {
  let baseClasses = `transition-all text-center flex items-center justify-center text-black no-underline font-black border-black `;
  let shadowClasses = "";

  if (size === "sm") {
    baseClasses += `text-xs py-1.5 px-2 border-[2px] `;
    shadowClasses = `shadow-[2px_2px_0px_rgba(0,0,0,1)] hover:shadow-[3px_3px_0px_rgba(0,0,0,1)] hover:translate-x-[-1px] hover:translate-y-[-1px] `;
  } else if (size === "md") {
    // ExportActions 风格
    baseClasses += `text-xs py-2.5 px-3 border-[2px] `;
    shadowClasses = `shadow-[2px_2px_0px_rgba(0,0,0,1)] hover:shadow-[4px_4px_0px_rgba(0,0,0,1)] hover:translate-x-[-2px] hover:translate-y-[-2px] `;
  } else if (size === "lg") {
    // 原 brutal-btn 风格
    baseClasses += `text-base px-6 py-3 border-[3px] rounded-md `;
    shadowClasses = `shadow-[4px_4px_0px_rgba(0,0,0,1)] hover:shadow-[6px_6px_0px_rgba(0,0,0,1)] hover:translate-x-[-2px] hover:translate-y-[-2px] `;
  }

  const activeClasses = `active:shadow-none active:translate-x-0 active:translate-y-0 `;
  const disabledClasses = `disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-[2px_2px_0px_rgba(0,0,0,1)] disabled:hover:translate-x-0 disabled:hover:translate-y-0 `;

  // 合并基础类和可能从外面传入覆盖的 shadow/translate 类
  const finalClassName = `${baseClasses} ${shadowClasses} ${activeClasses} ${disabledClasses} ${className}`;

  if (href) {
    return (
      <a
        id={id}
        href={disabled ? undefined : href}
        target="_blank"
        rel="noreferrer"
        className={`${finalClassName} ${disabled ? "opacity-40 cursor-not-allowed pointer-events-none" : ""}`}
        style={{ backgroundColor: accent }}
      >
        {children}
      </a>
    );
  }

  return (
    <button
      id={id}
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={finalClassName}
      style={{ backgroundColor: accent }}
    >
      {children}
    </button>
  );
}
