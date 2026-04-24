"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface VoiceDockProps {
  transcript: string;
  connected: boolean;
  onStartRecording: () => void;
  onStopRecording: () => void;
}

const NUM_BARS = 64;

export function VoiceDock({
  transcript,
  connected,
  onStartRecording,
  onStopRecording,
}: VoiceDockProps): React.JSX.Element {
  const [supported, setSupported] = useState<boolean>(false);
  const [recording, setRecording] = useState<boolean>(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const hasMR =
      typeof window.MediaRecorder !== "undefined" &&
      typeof navigator !== "undefined" &&
      typeof navigator.mediaDevices !== "undefined" &&
      typeof navigator.mediaDevices.getUserMedia === "function";
    setSupported(hasMR);
  }, []);

  const drawIdle = useCallback(() => {
    const canvas = canvasRef.current;
    if (canvas === null) return;
    const ctx = canvas.getContext("2d");
    if (ctx === null) return;
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#1e293b";
    const barWidth = width / NUM_BARS;
    for (let i = 0; i < NUM_BARS; i += 1) {
      const h = 2;
      ctx.fillRect(
        i * barWidth + 1,
        (height - h) / 2,
        Math.max(1, barWidth - 2),
        h,
      );
    }
  }, []);

  useEffect(() => {
    drawIdle();
  }, [drawIdle]);

  const tick = useCallback(() => {
    const analyser = analyserRef.current;
    const canvas = canvasRef.current;
    if (analyser === null || canvas === null) return;
    const ctx = canvas.getContext("2d");
    if (ctx === null) return;
    const bins = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(bins);
    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);
    const barWidth = width / NUM_BARS;
    const step = Math.floor(bins.length / NUM_BARS) || 1;
    for (let i = 0; i < NUM_BARS; i += 1) {
      const v = bins[i * step] ?? 0;
      const h = Math.max(2, (v / 255) * height);
      ctx.fillStyle = "#34d399";
      ctx.fillRect(
        i * barWidth + 1,
        (height - h) / 2,
        Math.max(1, barWidth - 2),
        h,
      );
    }
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const cleanupAudio = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (sourceRef.current !== null) {
      try {
        sourceRef.current.disconnect();
      } catch {
        /* ignore */
      }
      sourceRef.current = null;
    }
    if (streamRef.current !== null) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (audioCtxRef.current !== null) {
      audioCtxRef.current.close().catch(() => {
        /* ignore */
      });
      audioCtxRef.current = null;
    }
    analyserRef.current = null;
    drawIdle();
  }, [drawIdle]);

  const begin = useCallback(async () => {
    if (!supported || recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      streamRef.current = stream;
      const AC: typeof AudioContext =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      const ctx = new AC();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;
      source.connect(analyser);
      setRecording(true);
      onStartRecording();
      rafRef.current = requestAnimationFrame(tick);
    } catch {
      cleanupAudio();
      setRecording(false);
    }
  }, [supported, recording, tick, onStartRecording, cleanupAudio]);

  const end = useCallback(() => {
    if (!recording) return;
    setRecording(false);
    onStopRecording();
    cleanupAudio();
  }, [recording, onStopRecording, cleanupAudio]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === "Space" && !e.repeat) {
        const t = e.target as HTMLElement | null;
        if (
          t !== null &&
          (t.tagName === "INPUT" ||
            t.tagName === "TEXTAREA" ||
            t.isContentEditable)
        ) {
          return;
        }
        e.preventDefault();
        void begin();
      }
    };
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        e.preventDefault();
        end();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [begin, end]);

  useEffect(() => {
    return () => {
      cleanupAudio();
    };
  }, [cleanupAudio]);

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            Voice
          </h2>
          <span
            className={
              connected
                ? "inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300"
                : "inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300"
            }
          >
            <span
              className={
                connected
                  ? "h-1.5 w-1.5 rounded-full bg-emerald-400"
                  : "h-1.5 w-1.5 rounded-full bg-amber-400"
              }
            />
            {connected ? "Connected" : "Mock replay"}
          </span>
        </div>
        <div className="text-xs text-slate-500">
          Hold space or the button to talk
        </div>
      </div>

      <div className="mt-4 flex items-center gap-5">
        <button
          type="button"
          disabled={!supported}
          onMouseDown={() => {
            void begin();
          }}
          onMouseUp={end}
          onMouseLeave={() => {
            if (recording) end();
          }}
          onTouchStart={(e) => {
            e.preventDefault();
            void begin();
          }}
          onTouchEnd={(e) => {
            e.preventDefault();
            end();
          }}
          title={
            supported
              ? "Push and hold to talk"
              : "Microphone unavailable (SSR or unsupported browser)"
          }
          className={
            "relative flex h-16 w-16 shrink-0 items-center justify-center rounded-full border transition-colors " +
            (recording
              ? "border-emerald-400 bg-emerald-500/20 text-emerald-200"
              : supported
                ? "border-slate-700 bg-slate-800 text-slate-300 hover:border-emerald-500 hover:text-emerald-300"
                : "cursor-not-allowed border-slate-800 bg-slate-900 text-slate-600")
          }
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-7 w-7"
          >
            <rect x="9" y="2" width="6" height="12" rx="3" />
            <path d="M5 11a7 7 0 0 0 14 0" />
            <line x1="12" y1="19" x2="12" y2="22" />
          </svg>
          {recording ? (
            <span className="absolute inset-0 -z-10 animate-ping rounded-full bg-emerald-400/30" />
          ) : null}
        </button>

        <div className="flex-1">
          <canvas
            ref={canvasRef}
            width={720}
            height={72}
            className="h-[72px] w-full rounded-lg bg-slate-950/60"
          />
        </div>
      </div>

      <div className="mt-4 min-h-[2.25rem] rounded-lg border border-slate-800/80 bg-slate-950/40 px-4 py-2 text-sm text-slate-300">
        {transcript !== "" ? (
          <span>{transcript}</span>
        ) : (
          <span className="text-slate-600">
            Transcript will appear here...
          </span>
        )}
      </div>
    </section>
  );
}
