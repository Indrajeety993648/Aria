"use client";

import type { InboxItem } from "@/lib/contracts";
import { truncate } from "@/lib/format";
import { Panel } from "./Panel";

interface InboxPanelProps {
  inbox: InboxItem[];
}

function urgencyBar(u: number): string {
  const n = Math.round(u * 5);
  return "▮".repeat(n) + "▯".repeat(5 - n);
}

function sentimentMark(s: number): string {
  if (s <= -0.4) return "−−";
  if (s < 0) return "−";
  if (s > 0.4) return "++";
  if (s > 0) return "+";
  return "·";
}

export function InboxPanel({ inbox }: InboxPanelProps) {
  const urgent = inbox.filter((i) => i.urgency >= 0.85).length;

  return (
    <Panel
      label="INBOX // PRIO"
      meta={
        <span className="tracking-widest">
          <span className="text-(--color-fg-muted) mr-1">URG</span>
          <span
            className={`data ${
              urgent > 0
                ? "text-(--color-amber)"
                : "text-(--color-fg-dim)"
            }`}
          >
            {String(urgent).padStart(2, "0")}
          </span>
          <span className="text-(--color-fg-muted) mx-1">/</span>
          <span className="data text-(--color-fg-dim)">
            {String(inbox.length).padStart(2, "0")}
          </span>
        </span>
      }
      stateDot={urgent > 0 ? "warn" : "idle"}
      className="h-full"
    >
      <table className="w-full border-collapse text-[11px]">
        <thead className="sticky top-0 z-10 bg-(--color-panel-2) text-(--color-fg-muted)">
          <tr className="border-b border-(--color-border)">
            <th className="px-2 py-1 text-left tracking-widest font-normal">FROM</th>
            <th className="px-2 py-1 text-left tracking-widest font-normal">SUBJECT</th>
            <th className="px-2 py-1 text-right tracking-widest font-normal">URG</th>
            <th className="px-2 py-1 text-right tracking-widest font-normal">AGE</th>
            <th className="px-2 py-1 text-center tracking-widest font-normal">SENT</th>
          </tr>
        </thead>
        <tbody>
          {inbox.map((it) => {
            const urgent = it.urgency >= 0.85;
            return (
              <tr
                key={it.email_id}
                className={`border-b border-(--color-border)/60 hover:bg-(--color-hover) ${
                  urgent ? "" : ""
                }`}
              >
                <td className="px-2 py-1 text-(--color-fg-dim) data whitespace-nowrap">
                  {it.sender_id.replace("c_", "")}
                </td>
                <td className={`px-2 py-1 ${urgent ? "text-(--color-amber)" : "text-(--color-fg)"}`}>
                  {truncate(it.subject, 36)}
                  {!it.requires_reply && (
                    <span className="ml-2 text-[9px] text-(--color-fg-muted)">
                      [FYI]
                    </span>
                  )}
                </td>
                <td className="px-2 py-1 text-right data">
                  <span
                    className={
                      urgent
                        ? "text-(--color-amber)"
                        : it.urgency > 0.5
                          ? "text-(--color-fg-dim)"
                          : "text-(--color-fg-muted)"
                    }
                  >
                    {urgencyBar(it.urgency)}
                  </span>
                </td>
                <td className="px-2 py-1 text-right data text-(--color-fg-muted) whitespace-nowrap">
                  {it.age_hours < 1
                    ? `${Math.round(it.age_hours * 60)}m`
                    : `${it.age_hours.toFixed(1)}h`}
                </td>
                <td
                  className={`px-2 py-1 text-center data ${
                    it.sentiment <= -0.4
                      ? "text-(--color-red)"
                      : it.sentiment > 0.4
                        ? "text-(--color-phosphor)"
                        : "text-(--color-fg-muted)"
                  }`}
                >
                  {sentimentMark(it.sentiment)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
