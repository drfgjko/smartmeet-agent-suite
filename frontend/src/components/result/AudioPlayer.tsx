"use client";

import React, { useRef, useState, useEffect, useCallback, forwardRef, useImperativeHandle } from "react";

export type AudioPlayerHandle = {
  /** 跳转到指定秒数（供逐字稿联动调用） */
  seekTo: (seconds: number) => void;
};

type AudioPlayerProps = {
  /** 音频流 URL，例如 /api/v1/reports/{meeting_id}/audio */
  src: string;
  /** 当前播放时间变化回调（供外部逐字稿高亮用） */
  onTimeUpdate?: (currentTime: number) => void;
};

/** 将秒数格式化为 MM:SS */
function formatTime(secs: number): string {
  if (!isFinite(secs) || secs < 0) return "00:00";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

const AudioPlayer = forwardRef<AudioPlayerHandle, AudioPlayerProps>(
  ({ src, onTimeUpdate }, ref) => {
    const audioRef = useRef<HTMLAudioElement>(null);
    const progressRef = useRef<HTMLDivElement>(null);

    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [volume, setVolume] = useState(1);
    const [isDragging, setIsDragging] = useState(false);
    const [isLoaded, setIsLoaded] = useState(false);
    const [loadError, setLoadError] = useState(false);

    // 暴露 seekTo 给父组件（逐字稿点击联动）
    useImperativeHandle(ref, () => ({
      seekTo(seconds: number) {
        if (!audioRef.current) return;
        audioRef.current.currentTime = seconds;
        setCurrentTime(seconds);
        if (audioRef.current.paused) {
          audioRef.current.play().catch(() => {});
          setIsPlaying(true);
        }
      },
    }));

    const togglePlay = useCallback(() => {
      const audio = audioRef.current;
      if (!audio) return;
      if (audio.paused) {
        audio.play().catch(() => {});
        setIsPlaying(true);
      } else {
        audio.pause();
        setIsPlaying(false);
      }
    }, []);

    /** 根据点击/拖拽位置计算进度并跳转 */
    const seekFromEvent = useCallback(
      (e: React.MouseEvent | MouseEvent) => {
        const bar = progressRef.current;
        const audio = audioRef.current;
        if (!bar || !audio || !duration) return;
        const rect = bar.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        audio.currentTime = ratio * duration;
        setCurrentTime(audio.currentTime);
      },
      [duration]
    );

    // 进度条拖拽
    const handleProgressMouseDown = (e: React.MouseEvent) => {
      setIsDragging(true);
      seekFromEvent(e);
    };

    useEffect(() => {
      if (!isDragging) return;
      const onMove = (e: MouseEvent) => seekFromEvent(e);
      const onUp = () => setIsDragging(false);
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
      return () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
      };
    }, [isDragging, seekFromEvent]);

    // 音量
    const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const v = Number(e.target.value);
      setVolume(v);
      if (audioRef.current) audioRef.current.volume = v;
    };

    const percent = duration > 0 ? (currentTime / duration) * 100 : 0;

    return (
      <div className="brutal-box p-4 bg-white select-none">
        {/* 隐藏的 audio 元素 */}
        <audio
          ref={audioRef}
          src={src}
          preload="metadata"
          onLoadedMetadata={() => {
            setDuration(audioRef.current?.duration ?? 0);
            setIsLoaded(true);
            setLoadError(false);
          }}
          onTimeUpdate={() => {
            const t = audioRef.current?.currentTime ?? 0;
            setCurrentTime(t);
            onTimeUpdate?.(t);
          }}
          onEnded={() => setIsPlaying(false)}
          onError={() => setLoadError(true)}
        />

        {loadError ? (
          <p className="text-sm font-bold text-red-600 py-2 text-center">
            音频加载失败，请确认后端音频接口正常。
          </p>
        ) : (
          <>
            {/* 时间戳行 */}
            <div className="flex justify-between text-xs font-bold text-gray-500 mb-2">
              <span>{formatTime(currentTime)}</span>
              <span>{isLoaded ? formatTime(duration) : "--:--"}</span>
            </div>

            {/* 进度条 */}
            <div
              ref={progressRef}
              className="relative h-3 bg-gray-200 border-[2px] border-black rounded cursor-pointer mb-4"
              onMouseDown={handleProgressMouseDown}
            >
              {/* 已播放填充 */}
              <div
                className="absolute top-0 left-0 h-full bg-black rounded"
                style={{ width: `${percent}%`, transition: isDragging ? "none" : "width 0.1s linear" }}
              />
              {/* 拖拽手柄 */}
              <div
                className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-[#ffc900] border-[2px] border-black rounded-sm shadow-[2px_2px_0px_rgba(0,0,0,1)]"
                style={{ left: `calc(${percent}% - 8px)`, transition: isDragging ? "none" : "left 0.1s linear" }}
              />
            </div>

            {/* 控制区 */}
            <div className="flex items-center gap-3">
              {/* 播放/暂停按钮 */}
              <button
                id="audio-play-pause-btn"
                onClick={togglePlay}
                disabled={!isLoaded}
                className="brutal-btn w-11 h-11 flex items-center justify-center bg-black text-white hover:bg-[#ffc900] hover:text-black disabled:opacity-40 text-lg p-0"
                aria-label={isPlaying ? "暂停" : "播放"}
              >
                {isPlaying ? (
                  /* 暂停图标 */
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <rect x="3" y="2" width="4" height="12" rx="1" />
                    <rect x="9" y="2" width="4" height="12" rx="1" />
                  </svg>
                ) : (
                  /* 播放图标 */
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M4 2.5v11l9-5.5-9-5.5z" />
                  </svg>
                )}
              </button>

              {/* 音量 */}
              <div className="flex items-center gap-1 ml-auto">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-gray-500 flex-shrink-0">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  {volume > 0 && <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />}
                  {volume > 0.5 && <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />}
                </svg>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={volume}
                  onChange={handleVolumeChange}
                  className="w-20 h-1 accent-black cursor-pointer"
                  aria-label="音量"
                />
              </div>
            </div>
          </>
        )}
      </div>
    );
  }
);

AudioPlayer.displayName = "AudioPlayer";
export default AudioPlayer;
