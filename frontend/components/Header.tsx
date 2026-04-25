"use client";

import { useEffect, useState } from "react";
import { clock, formatSession, pad } from "@/lib/format";
import type { ConnectionState } from "@/lib/ws";

interface HeaderProps {
  sessionId: string;
  connected: ConnectionState;
  tickCount: number;
  latencyMs: number;
  scenarioCategory?: string | null;
  difficulty?: string | null;
}

const CONN_LABEL: Record<ConnectionState, string> = {
  connecting: "LINK…",
  live: "LIVE",
  mock: "OFFLINE",
  error: "FAULT",
};

const CONN_DOT: Record<ConnectionState, "live" | "idle" | "warn" | "err"> = {
  connecting: "warn",
  live: "live",
  mock: "idle",
  error: "err",
};

export function Header({
  sessionId,
  connected,
  tickCount,
  latencyMs,
  scenarioCategory,
  difficulty,
}: HeaderProps) {
  // SSR-safe: start empty, populate after mount so server + client agree.
  const [utc, setUtc] = useState("");
  useEffect(() => {
    setUtc(clock());
    const id = setInterval(() => setUtc(clock()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="hairline-b flex h-7 items-center justify-between bg-(--color-panel-2) px-3">
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-2">
          <span className="text-(--color-amber) font-bold tracking-[0.22em]">
            ARIA
          </span>
          <span className="text-(--color-fg-muted) text-[10px] tracking-[0.14em]">
            / v0.1 / AGENTIC RUNTIME
          </span>
        </span>
        <span className="text-[10px] tracking-widest text-(--color-fg-muted)">
          <span className="mr-1">SES</span>
          <span
            className="text-(--color-fg-dim) data"
            suppressHydrationWarning
          >
            {sessionId ? formatSession(sessionId) : "--------"}
          </span>
        </span>
        <span className="text-[10px] tracking-widest text-(--color-fg-muted)">
          <span className="mr-1">ENV</span>
          <span className="text-(--color-fg-dim)">
            {(scenarioCategory ?? "IDLE").toString().toUpperCase()}
          </span>
          {difficulty && (
            <span className="ml-1 text-(--color-fg-muted)">
              [{difficulty.toString().toUpperCase()}]
            </span>
          )}
        </span>
      </div>
      <div className="flex items-center gap-5">
        <span className="text-[10px] tracking-widest text-(--color-fg-muted)">
          <span className="mr-1">TICK</span>
          <span className="text-(--color-phosphor) data">{pad(tickCount, 4)}</span>
        </span>
        <span className="text-[10px] tracking-widest text-(--color-fg-muted)">
          <span className="mr-1">P95</span>
          <span
            className={`data ${
              latencyMs < 500 ? "text-(--color-phosphor)" : "text-(--color-red)"
            }`}
          >
            {pad(latencyMs, 3)}MS
          </span>
        </span>
        <span className="flex items-center gap-1.5 text-[10px] tracking-widest">
          <span className={`dot dot-${CONN_DOT[connected]}`} aria-hidden />
          <span
            className={
              connected === "live"
                ? "text-(--color-phosphor)"
                : connected === "error"
                  ? "text-(--color-red)"
                  : "text-(--color-amber)"
            }
          >
            {CONN_LABEL[connected]}
          </span>
        </span>
        <span
          className="text-[10px] tracking-widest text-(--color-fg-muted) data"
          suppressHydrationWarning
        >
          {utc || "--:--:--Z"}
        </span>
      </div>
    </header>
  );
}
