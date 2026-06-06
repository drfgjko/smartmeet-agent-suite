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
      className={`border-[3px] border-black p-12 text-center transition-all cursor-pointer ${
        dragOver
          ? "bg-[#ffc900] shadow-[inset_4px_4px_0px_0px_rgba(0,0,0,1)]"
          : "bg-white hover:bg-[#f4f4f0] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]"
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
        <div className="space-y-4">
          <div className="w-16 h-16 mx-auto border-[3px] border-black bg-[#22d3ee] flex items-center justify-center shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            <span className="font-black text-xl">OK</span>
          </div>
          <p className="font-black text-xl">{uploadFile.name}</p>
          <p className="text-sm font-bold text-gray-600">
            {(uploadFile.size / 1024 / 1024).toFixed(1)} MB · 点击重新选择
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="w-16 h-16 mx-auto border-[3px] border-black bg-white flex items-center justify-center shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
            <span className="font-black text-2xl">+</span>
          </div>
          <p className="text-xl font-black">拖拽音视频文件到此处，或点击选择</p>
          <p className="text-sm font-bold text-gray-600">支持 MP4 / MP3 / WAV / M4A 等</p>
        </div>
      )}
    </div>
  );
}
