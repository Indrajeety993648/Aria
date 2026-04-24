"use client";

import { useEffect, useRef } from "react";
import type { GwAgentEvent, GwEventKind } from "@/lib/contracts";

interface EventTraceProps {
  events: GwAgentEvent[];
}

const KIND_CLASS: Readonly<Record<GwEventKind, string>> = {
  session_start: "bg-slate-700/30 text-slate-300 border-slate-600/40",
  partial_transcript: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  final_transcript: "bg-sky-500/25 text-sky-200 border-sky-500/40",
  tool_call: "bg-violet-500/15 text-violet-300 border-violet-500/30",
  reply_text: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  tts_chunk: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  env_step: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  reward: "bg-emerald-400/20 text-emerald-200 border-emerald-400/40",
  error: "bg-red-500/15 text-red-300 border-red-500/30",
};

function formatTs(ts: number): string {
  const d = new Date(ts);
  const pad = (n: number, w = 2): string => n.toString().padStart(w, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : `${s.slice(0, n - 1)}…`;
}

export function EventTrace({ events }: EventTraceProps): React.JSX.Element {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el !== null) {
      el.scrollTop = el.scrollHeight;
    }
  }, [events]);

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Event trace
        </h2>
        <span className="text-xs text-slate-500">
          {events.length} event{events.length === 1 ? "" : "s"}
        </span>
      </div>
      <div
        ref={scrollRef}
        className="mt-3 max-h-[320px] overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/50 p-2 font-mono text-[12px] leading-relaxed"
      >
        {events.length === 0 ? (
          <div className="p-3 text-slate-600">No events yet...</div>
        ) : (
          <ul className="flex flex-col gap-1">
            {events.map((ev, idx) => {
              const payloadJson = truncate(JSON.stringify(ev.payload), 160);
              return (
                <li
                  key={`${ev.ts_ms}-${idx}`}
                  className="flex items-start gap-2 px-2 py-1"
                >
                  <span className="w-[100px] shrink-0 text-slate-600">
                    {formatTs(ev.ts_ms)}
                  </span>
                  <span
                    className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${KIND_CLASS[ev.kind]}`}
                  >
                    {ev.kind}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-slate-300">
                    {payloadJson}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
