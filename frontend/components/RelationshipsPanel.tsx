"use client";

import type { RelationshipNode } from "@/lib/contracts";
import { Panel } from "./Panel";

interface RelationshipsPanelProps {
  relationships: RelationshipNode[];
}

function closenessBar(c: number): string {
  const n = Math.round(c * 8);
  return "█".repeat(n) + "·".repeat(8 - n);
}

function neglectMark(hours: number): string {
  if (hours > 96) return "◼";
  if (hours > 48) return "◉";
  if (hours > 12) return "·";
  return " ";
}

export function RelationshipsPanel({ relationships }: RelationshipsPanelProps) {
  const neglected = relationships.filter(
    (r) => r.last_contact_hours > 48 && r.closeness >= 0.7,
  ).length;

  return (
    <Panel
      label="CONTACTS // GRAPH"
      meta={
        <span className="tracking-widest">
          <span className="text-(--color-fg-muted) mr-1">NGLCT</span>
          <span
            className={`data ${
              neglected > 0
                ? "text-(--color-red)"
                : "text-(--color-fg-dim)"
            }`}
          >
            {String(neglected).padStart(2, "0")}
          </span>
          <span className="text-(--color-fg-muted) mx-1">/</span>
          <span className="data text-(--color-fg-dim)">
            {String(relationships.length).padStart(2, "0")}
          </span>
        </span>
      }
      stateDot={neglected > 0 ? "warn" : "idle"}
      className="h-full"
    >
      <table className="w-full border-collapse text-[11px]">
        <thead className="sticky top-0 z-10 bg-(--color-panel-2) text-(--color-fg-muted)">
          <tr className="border-b border-(--color-border)">
            <th className="px-2 py-1 text-left tracking-widest font-normal">NAME</th>
            <th className="px-2 py-1 text-left tracking-widest font-normal">ROLE</th>
            <th className="px-2 py-1 text-left tracking-widest font-normal">CLOSE</th>
            <th className="px-2 py-1 text-right tracking-widest font-normal">TRUST</th>
            <th className="px-2 py-1 text-right tracking-widest font-normal">LAST</th>
            <th className="px-2 py-1 text-left tracking-widest font-normal">TONE</th>
          </tr>
        </thead>
        <tbody>
          {relationships.map((r) => {
            const stale = r.last_contact_hours > 48 && r.closeness >= 0.7;
            return (
              <tr
                key={r.contact_id}
                className="border-b border-(--color-border)/60 hover:bg-(--color-hover)"
              >
                <td className="px-2 py-1 text-(--color-fg)">
                  <span
                    className={`mr-1 ${
                      stale
                        ? "text-(--color-red)"
                        : "text-(--color-fg-muted)"
                    }`}
                  >
                    {neglectMark(r.last_contact_hours)}
                  </span>
                  {r.name}
                </td>
                <td className="px-2 py-1 text-(--color-fg-muted) uppercase text-[10px] tracking-widest">
                  {r.relationship_kind}
                </td>
                <td className="px-2 py-1 data text-(--color-amber)">
                  {closenessBar(r.closeness)}
                </td>
                <td className="px-2 py-1 text-right data text-(--color-fg-dim)">
                  {r.trust.toFixed(2)}
                </td>
                <td
                  className={`px-2 py-1 text-right data ${
                    stale
                      ? "text-(--color-red)"
                      : "text-(--color-fg-muted)"
                  } whitespace-nowrap`}
                >
                  {r.last_contact_hours < 24
                    ? `${r.last_contact_hours.toFixed(0)}h`
                    : `${(r.last_contact_hours / 24).toFixed(1)}d`}
                </td>
                <td className="px-2 py-1 text-(--color-cyan) text-[10px] tracking-widest uppercase">
                  {r.tone_preference}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
