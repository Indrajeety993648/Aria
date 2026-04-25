"use client";

import type { ReactNode } from "react";

export interface PanelProps {
  label: string;
  meta?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  scanning?: boolean;
  gridBg?: boolean;
  className?: string;
  bodyClassName?: string;
  stateDot?: "live" | "idle" | "warn" | "err";
}

export function Panel({
  label,
  meta,
  footer,
  children,
  scanning,
  gridBg,
  className = "",
  bodyClassName = "",
  stateDot = "idle",
}: PanelProps) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-header">
        <div className="flex items-center gap-2">
          <span className={`dot dot-${stateDot}`} aria-hidden />
          <span className="bracket text-(--color-fg-dim) font-semibold">
            {label}
          </span>
        </div>
        {meta && (
          <div className="text-(--color-fg-muted)">
            {meta}
          </div>
        )}
      </header>
      {scanning && <div className="scan-bar" aria-hidden />}
      <div
        className={`panel-body ${gridBg ? "panel-grid-bg" : ""} ${bodyClassName}`}
      >
        {children}
      </div>
      {footer && (
        <footer className="hairline-t px-2.5 py-1 text-[10px] uppercase tracking-widest text-(--color-fg-muted)">
          {footer}
        </footer>
      )}
    </section>
  );
}
