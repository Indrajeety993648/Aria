"use client";

import { useEffect, useMemo, useRef } from "react";
import type { GwAgentEvent, GwEventKind } from "@/lib/contracts";
import { Panel } from "./Panel";

const KIND_COLOR: Record<GwEventKind, string> = {
  session_start:    "text-(--color-fg-dim)",
  partial_transcript:"text-(--color-fg-muted)",
  final_transcript: "text-(--color-fg)",
  tool_call:        "text-(--color-cyan)",
  reply_text:       "text-(--color-amber)",
  tts_chunk:        "text-(--color-fg-muted)",
  env_step:         "text-(--color-phosphor)",
  reward:           "text-(--color-phosphor)",
  error:            "text-(--color-red)",
};

const KIND_ABBR: Record<GwEventKind, string> = {
  session_start:    "SES",
  partial_transcript:"PARTL",
  final_transcript: "FINAL",
  tool_call:        "TOOL",
  reply_text:       "REPLY",
  tts_chunk:        "TTS",
  env_step:         "STEP",
  reward:           "RWD",
  error:            "ERR",
};

interface EventTraceProps {
  events: GwAgentEvent[];
}

function previewPayload(ev: GwAgentEvent): string {
  const p = ev.payload ?? {};
  if (typeof p === "object") {
    if ("text" in p && typeof p.text === "string") return p.text;
    if ("tool_name" in p) {
      const args =
        "arguments" in p && p.arguments
          ? JSON.stringify(p.arguments).slice(0, 40)
          : "";
      return `${p.tool_name as string} ${args}`;
    }
    if ("action" in p) {
      const tgt = "target" in p ? ` → ${p.target as string}` : "";
      return `${p.action as string}${tgt}`;
    }
    if ("total" in p) {
      return `Δ=${Number(p.total).toFixed(3)}`;
    }
    const s = JSON.stringify(p);
    return s.length > 80 ? s.slice(0, 77) + "…" : s;
  }
  return String(p);
}

function tsLabel(ts: number): string {
  const d = new Date(ts);
  const h = String(d.getUTCHours()).padStart(2, "0");
  const m = String(d.getUTCMinutes()).padStart(2, "0");
  const s = String(d.getUTCSeconds()).padStart(2, "0");
  const ms = String(d.getUTCMilliseconds()).padStart(3, "0");
  return `${h}:${m}:${s}.${ms}`;
}

export function EventTrace({ events }: EventTraceProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const rows = useMemo(() => events.slice().reverse(), [events]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [events.length]);

  return (
    <Panel
      label="EVENT // TRACE"
      meta={
        <span className="tracking-widest">
          <span className="text-(--color-fg-muted) mr-1">N</span>
          <span className="data text-(--color-fg-dim)">
            {String(events.length).padStart(4, "0")}
          </span>
        </span>
      }
      stateDot="live"
      className="h-full"
    >
      <div ref={scrollRef} className="h-full overflow-auto">
        <table className="w-full border-collapse text-[11px]">
          <thead className="sticky top-0 z-10 bg-(--color-panel-2) text-(--color-fg-muted)">
            <tr className="border-b border-(--color-border)">
              <th className="px-2 py-1 text-left tracking-widest font-normal">TS</th>
              <th className="px-2 py-1 text-left tracking-widest font-normal">KIND</th>
              <th className="px-2 py-1 text-left tracking-widest font-normal">PAYLOAD</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((ev, i) => (
              <tr
                key={`${ev.ts_ms}-${i}`}
                className="border-b border-(--color-border)/60 hover:bg-(--color-hover)"
              >
                <td className="px-2 py-1 align-top text-(--color-fg-muted) data">
                  {tsLabel(ev.ts_ms)}
                </td>
                <td className="px-2 py-1 align-top">
                  <span
                    className={`inline-block w-[48px] text-center font-bold tracking-widest ${KIND_COLOR[ev.kind]}`}
                  >
                    {KIND_ABBR[ev.kind]}
                  </span>
                </td>
                <td className="px-2 py-1 align-top text-(--color-fg-dim) break-all">
                  {previewPayload(ev)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
