import React from "react";

export type BrutalCheckboxProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: React.ReactNode;
  disabled?: boolean;
  title?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
  style?: React.CSSProperties;
};

export default function BrutalCheckbox({
  checked,
  onChange,
  label,
  disabled = false,
  title,
  size = "md",
  className = "",
  style,
}: BrutalCheckboxProps) {
  // 定义不同尺寸的基础样式映射
  const sizeMap = {
    sm: {
      gap: "gap-1.5",
      box: "w-3.5 h-3.5 border-[1.5px]",
      text: "text-[11px]",
    },
    md: {
      gap: "gap-2",
      box: "w-4 h-4 border-2",
      text: "text-xs",
    },
    lg: {
      gap: "gap-3",
      box: "w-5 h-5 border-2",
      text: "text-sm",
    },
  };

  const currentSize = sizeMap[size];

  return (
    <label
      className={`flex items-center ${currentSize.gap} ${
        disabled
          ? "cursor-not-allowed opacity-50"
          : "cursor-pointer hover:text-black transition-colors"
      } ${className}`}
      style={style}
      title={title}
    >
      <input
        type="checkbox"
        disabled={disabled}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className={`${currentSize.box} border-black accent-black cursor-inherit`}
      />
      <span className={`font-bold ${currentSize.text}`}>{label}</span>
    </label>
  );
}
