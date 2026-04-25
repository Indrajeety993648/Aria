"use client";

import { useEffect, useRef, useState } from "react";

interface BootSequenceProps {
  onComplete: () => void;
}

// Per-line dwell times are intentionally uneven — the microsecond-level
// variance makes the boot feel like a real system doing real work, not a
// uniform animation. Total dwell ≈ 2.9s; with reveal + fade ≈ 4.2s.
const LINES: { label: string; delay: number }[] = [
  { label: "initializing agent runtime",            delay: 340 },
  { label: "loading env: aria-personal-manager-v1", delay: 420 },
  { label: "spawning microservices (5)",            delay: 380 },
  { label: "connecting gateway ws",                 delay: 460 },
  { label: "calibrating microphone",                delay: 400 },
  { label: "loading relationship graph (9 nodes)",  delay: 360 },
  { label: "policy → scripted-expert baseline",     delay: 440 },
];

const PROMPT = "› ";

export function BootSequence({ onComplete }: BootSequenceProps) {
  const [shown, setShown] = useState(0);
  const [done, setDone] = useState(false);
  const [hidden, setHidden] = useState(false);

  // Keep the latest callback in a ref so the boot-timer effect can run
  // exactly once on mount without being invalidated every time the parent
  // re-renders and hands us a new onComplete identity.
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    // Initial pause — masthead breathes before the first line prints.
    let acc = 350;
    for (let i = 0; i < LINES.length; i++) {
      acc += LINES[i].delay;
      timers.push(
        setTimeout(() => {
          if (!cancelled) setShown(i + 1);
        }, acc),
      );
    }
    // Beat after the last OK before "SYSTEM READY" lands.
    timers.push(
      setTimeout(() => {
        if (!cancelled) setDone(true);
      }, acc + 450),
    );
    // Let "SYSTEM READY" sit visible for a moment before the fade starts.
    timers.push(
      setTimeout(() => {
        if (!cancelled) setHidden(true);
      }, acc + 1100),
    );
    // Fade completes, then hand off to the main UI.
    timers.push(
      setTimeout(() => {
        if (!cancelled) onCompleteRef.current();
      }, acc + 1650),
    );
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
    };
    // Empty deps on purpose — this effect manages a one-shot timer chain
    // and must not restart when the parent re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex bg-black px-10 py-10"
      style={{
        opacity: hidden ? 0 : 1,
        transition: "opacity 380ms ease-out",
        pointerEvents: hidden ? "none" : "auto",
      }}
      aria-hidden={hidden}
    >
      <div className="m-auto w-full max-w-[640px] font-mono text-[12px] leading-[1.55]">
        {/* masthead */}
        <div className="flex items-baseline gap-3">
          <span className="text-(--color-amber) font-bold tracking-[0.34em] text-[15px]">
            ARIA
          </span>
          <span className="text-(--color-fg-muted) text-[10px] tracking-[0.22em]">
            // AGENTIC REAL-TIME INTELLIGENT ASSISTANT
          </span>
          <span className="ml-auto text-(--color-fg-muted) text-[10px] tracking-widest">
            v0.1.0
          </span>
        </div>
        <div className="mt-1 h-px w-full bg-(--color-border-strong)" />

        {/* boot lines */}
        <div className="mt-5 space-y-[3px]">
          {LINES.slice(0, shown).map((line, i) => (
            <div key={i} className="flex items-baseline gap-2 text-(--color-fg-dim)">
              <span className="text-(--color-amber)">{PROMPT}</span>
              <span className="flex-1">{line.label} …</span>
              <span className="text-(--color-phosphor) font-semibold">OK</span>
            </div>
          ))}
          {shown < LINES.length && (
            <div className="flex items-baseline gap-2 text-(--color-fg-dim)">
              <span className="text-(--color-amber)">{PROMPT}</span>
              <span className="flex-1">
                {LINES[shown].label} …<span className="cursor" />
              </span>
            </div>
          )}
          {done && (
            <div
              className="mt-5 flex items-center gap-2 text-(--color-phosphor)"
              style={{ animation: "aria-slide-in 260ms ease-out both" }}
            >
              <span className="dot dot-live" />
              <span className="font-bold tracking-widest">
                SYSTEM READY. STANDBY.
              </span>
            </div>
          )}
        </div>

        {/* bottom stamp */}
        <div className="mt-8 flex items-center justify-between text-(--color-fg-muted) text-[10px] tracking-widest">
          <span>meta pytorch openenv hackathon 2026</span>
          <span>build: aria-0.1.0-alpha</span>
        </div>
      </div>
    </div>
  );
}
