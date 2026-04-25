"use client";

import { clock } from "@/lib/format";
import { useEffect, useState } from "react";

interface StatusBarProps {
  modeText: string;
  hotkeys?: [string, string][];
}

const DEFAULT_KEYS: [string, string][] = [
  ["M", "MUTE"],
  ["F1", "HELP"],
  ["F2", "RESET"],
  ["F3", "SCENARIO"],
  ["F4", "DIFFICULTY"],
  ["F10", "QUIT"],
];

export function StatusBar({ modeText, hotkeys = DEFAULT_KEYS }: StatusBarProps) {
  // SSR-safe clock.
  const [now, setNow] = useState("");
  useEffect(() => {
    setNow(clock());
    const id = setInterval(() => setNow(clock()), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <footer className="hairline-t flex h-6 items-center justify-between bg-(--color-panel-2) px-3 text-[10px] tracking-widest">
      <div className="flex items-center gap-5 text-(--color-fg-muted)">
        {hotkeys.map(([k, v]) => (
          <span key={k} className="inline-flex items-center gap-1">
            <span className="border border-(--color-border-strong) px-1 text-(--color-amber)">
              {k}
            </span>
            <span className="text-(--color-fg-dim)">{v}</span>
          </span>
        ))}
      </div>
      <div className="flex items-center gap-4 text-(--color-fg-muted)">
        <span className="text-(--color-fg-dim)">{modeText}</span>
        <span
          className="data text-(--color-fg-dim)"
          suppressHydrationWarning
        >
          {now || "--:--:--Z"}
        </span>
      </div>
    </footer>
  );
}
