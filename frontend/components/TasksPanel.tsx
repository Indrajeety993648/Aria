"use client";

import type { PendingTask } from "@/lib/contracts";
import { truncate } from "@/lib/format";
import { Panel } from "./Panel";

interface TasksPanelProps {
  tasks: PendingTask[];
}

function statusBadge(t: PendingTask): { text: string; color: string } {
  if (t.status === "done") return { text: "DONE",  color: "text-(--color-phosphor)" };
  if (t.status === "blocked") return { text: "BLK",   color: "text-(--color-red)" };
  if (t.status === "assigned") return { text: "ASSGN", color: "text-(--color-cyan)" };
  if (t.deadline_hours < 0) return { text: "OVRDUE", color: "text-(--color-red)" };
  if (t.deadline_hours < 4) return { text: "SOON",  color: "text-(--color-amber)" };
  return { text: "OPEN", color: "text-(--color-fg-dim)" };
}

export function TasksPanel({ tasks }: TasksPanelProps) {
  const overdue = tasks.filter((t) => t.deadline_hours < 0 && t.status === "open").length;

  return (
    <Panel
      label="TASKS // QUEUE"
      meta={
        <span className="tracking-widest">
          <span className="text-(--color-fg-muted) mr-1">OVR</span>
          <span
            className={`data ${
              overdue > 0
                ? "text-(--color-red)"
                : "text-(--color-fg-dim)"
            }`}
          >
            {String(overdue).padStart(2, "0")}
          </span>
          <span className="text-(--color-fg-muted) mx-1">/</span>
          <span className="data text-(--color-fg-dim)">
            {String(tasks.length).padStart(2, "0")}
          </span>
        </span>
      }
      stateDot={overdue > 0 ? "err" : "idle"}
      className="h-full"
    >
      <table className="w-full border-collapse text-[11px]">
        <thead className="sticky top-0 z-10 bg-(--color-panel-2) text-(--color-fg-muted)">
          <tr className="border-b border-(--color-border)">
            <th className="px-2 py-1 text-left tracking-widest font-normal">STAT</th>
            <th className="px-2 py-1 text-left tracking-widest font-normal">TITLE</th>
            <th className="px-2 py-1 text-right tracking-widest font-normal">PRI</th>
            <th className="px-2 py-1 text-right tracking-widest font-normal">DUE</th>
            <th className="px-2 py-1 text-center tracking-widest font-normal">DEL</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((t) => {
            const b = statusBadge(t);
            return (
              <tr
                key={t.task_id}
                className="border-b border-(--color-border)/60 hover:bg-(--color-hover)"
              >
                <td className={`px-2 py-1 data ${b.color}`}>{b.text}</td>
                <td className="px-2 py-1 text-(--color-fg)">
                  {truncate(t.title, 32)}
                </td>
                <td className="px-2 py-1 text-right data text-(--color-fg-dim)">
                  {t.priority.toFixed(2)}
                </td>
                <td
                  className={`px-2 py-1 text-right data ${
                    t.deadline_hours < 0
                      ? "text-(--color-red)"
                      : t.deadline_hours < 4
                        ? "text-(--color-amber)"
                        : "text-(--color-fg-muted)"
                  }`}
                >
                  {t.deadline_hours < 0
                    ? `${Math.abs(t.deadline_hours).toFixed(0)}h!`
                    : `${t.deadline_hours.toFixed(0)}h`}
                </td>
                <td
                  className={`px-2 py-1 text-center ${
                    t.delegatable
                      ? "text-(--color-cyan)"
                      : "text-(--color-fg-muted)"
                  }`}
                >
                  {t.delegatable ? "Y" : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
