import React, { useRef, useState } from 'react';

type FileInputProps = {
  uploadFile: File | null;
  setUploadFile: (file: File | null) => void;
};

export default function FileInput({ uploadFile, setUploadFile }: FileInputProps) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) setUploadFile(file);
  };

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer ${
        dragOver
          ? "border-[var(--accent)] bg-blue-50 dark:bg-blue-900/20 scale-[1.01]"
          : "border-[var(--border)] hover:border-[var(--text-secondary)]"
      }`}
      onClick={() => fileInputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*,video/*"
        className="hidden"
        onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
      />
      {uploadFile ? (
        <div className="space-y-3 animate-in zoom-in-95">
          <span className="text-4xl block">🎬</span>
          <p className="font-bold text-lg">{uploadFile.name}</p>
          <p className="text-sm text-[var(--text-secondary)]">
            {(uploadFile.size / 1024 / 1024).toFixed(1)} MB · 点击重新选择
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <span className="text-4xl block">📂</span>
          <p className="text-base font-medium">拖拽音视频文件到此处，或点击选择</p>
          <p className="text-sm text-[var(--text-secondary)]">支持 MP4 / MP3 / WAV / M4A 等</p>
        </div>
      )}
    </div>
  );
}
