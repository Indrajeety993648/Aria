"use client";

import type { CalendarEvent } from "@/lib/contracts";
import { dayLabel, hhmm, truncate } from "@/lib/format";
import { Panel } from "./Panel";

interface CalendarPanelProps {
  calendar: CalendarEvent[];
  currentTime: number;
}

function eventColor(ev: CalendarEvent): string {
  if (ev.event_id.startsWith("conflict_")) return "text-(--color-red)";
  if (ev.priority >= 0.85) return "text-(--color-amber)";
  if (ev.priority >= 0.6) return "text-(--color-fg)";
  return "text-(--color-fg-dim)";
}

export function CalendarPanel({ calendar, currentTime }: CalendarPanelProps) {
  // Detect overlaps on day 0 for the conflict indicator
  const day0 = calendar.filter((e) => e.day_offset === 0);
  const conflicts = day0.some((a, i) =>
    day0.slice(i + 1).some(
      (b) => a.start_hour < b.end_hour && b.start_hour < a.end_hour,
    ),
  );

  const sorted = [...calendar].sort(
    (a, b) => a.day_offset - b.day_offset || a.start_hour - b.start_hour,
  );

  return (
    <Panel
      label="CAL // NEXT 30D"
      meta={
        <span className="flex items-center gap-3 tracking-widest">
          <span>
            <span className="text-(--color-fg-muted) mr-1">N</span>
            <span className="data text-(--color-fg-dim)">
              {String(calendar.length).padStart(3, "0")}
            </span>
          </span>
          {conflicts && (
            <span className="text-(--color-red) data">● CONFLICT D0</span>
          )}
          <span>
            <span className="text-(--color-fg-muted) mr-1">T</span>
            <span className="data text-(--color-amber)">
              {hhmm(currentTime)}
            </span>
          </span>
        </span>
      }
      stateDot={conflicts ? "warn" : "idle"}
      className="h-full"
    >
      <table className="w-full border-collapse text-[11px]">
        <thead className="sticky top-0 z-10 bg-(--color-panel-2) text-(--color-fg-muted)">
          <tr className="border-b border-(--color-border)">
            <th className="px-2 py-1 text-left tracking-widest font-normal">DAY</th>
            <th className="px-2 py-1 text-left tracking-widest font-normal">WHEN</th>
            <th className="px-2 py-1 text-left tracking-widest font-normal">TITLE</th>
            <th className="px-2 py-1 text-right tracking-widest font-normal">PRI</th>
            <th className="px-2 py-1 text-right tracking-widest font-normal">FLX</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((ev) => {
            const ongoing =
              ev.day_offset === 0 &&
              currentTime >= ev.start_hour &&
              currentTime < ev.end_hour;
            return (
              <tr
                key={ev.event_id}
                className={`border-b border-(--color-border)/60 hover:bg-(--color-hover) ${
                  ongoing ? "bg-(--color-amber-ghost)/40" : ""
                }`}
              >
                <td className="px-2 py-1 text-(--color-fg-muted) data">
                  {dayLabel(ev.day_offset)}
                </td>
                <td className="px-2 py-1 text-(--color-fg-dim) data whitespace-nowrap">
                  {hhmm(ev.start_hour)}–{hhmm(ev.end_hour)}
                </td>
                <td className={`px-2 py-1 ${eventColor(ev)}`}>
                  {truncate(ev.title, 32)}
                  {ev.participant_ids.length > 0 && (
                    <span className="ml-2 text-(--color-fg-muted)">
                      w/ {ev.participant_ids[0].replace("c_", "")}
                      {ev.participant_ids.length > 1
                        ? `+${ev.participant_ids.length - 1}`
                        : ""}
                    </span>
                  )}
                </td>
                <td className="px-2 py-1 text-right data text-(--color-fg-dim)">
                  {ev.priority.toFixed(2)}
                </td>
                <td className="px-2 py-1 text-right data text-(--color-fg-muted)">
                  {ev.flexibility.toFixed(2)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
