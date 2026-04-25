"use client";

import { sign, pct } from "@/lib/format";
import type { AriaObservation, RewardBreakdown } from "@/lib/contracts";

interface TickerProps {
  observation: AriaObservation;
  runningReward: RewardBreakdown;
}

function Item({
  k,
  v,
  color = "text-(--color-fg-dim)",
}: { k: string; v: string; color?: string }) {
  return (
    <span className="mx-4 inline-flex items-baseline gap-1.5 whitespace-nowrap">
      <span className="text-[10px] text-(--color-fg-muted) tracking-widest">
        {k}
      </span>
      <span className={`text-xs data ${color}`}>{v}</span>
    </span>
  );
}

export function Ticker({ observation, runningReward }: TickerProps) {
  const inboxTotal = observation.inbox.length;
  const urgent = observation.inbox.filter((i) => i.urgency >= 0.85).length;
  const overdue = observation.pending_tasks.filter((t) => t.deadline_hours < 0).length;
  const open = observation.pending_tasks.filter((t) => t.status === "open").length;
  const closeContacts = observation.relationships.filter((r) => r.closeness >= 0.8).length;

  const items = (
    <>
      <Item k="R.Σ"  v={sign(runningReward.total, 2)} color="text-(--color-phosphor)" />
      <Item k="R.TASK" v={sign(runningReward.task_completion, 2)} />
      <Item k="R.REL"  v={sign(runningReward.relationship_health, 2)} />
      <Item k="R.SAT"  v={sign(runningReward.user_satisfaction, 2)} />
      <Item k="R.TIME" v={sign(runningReward.time_efficiency, 2)} />
      <Item k="R.CONF" v={sign(runningReward.conflict_resolution, 2)} />
      <Item k="R.SAFE" v={sign(runningReward.safety, 2)} />
      <span className="mx-4 text-(--color-fg-ghost)">│</span>
      <Item k="INBOX"   v={`${urgent}/${inboxTotal}`} color={urgent > 0 ? "text-(--color-amber)" : "text-(--color-fg-dim)"} />
      <Item k="TASKS"   v={`${overdue}OVR / ${open}OPN`} color={overdue > 0 ? "text-(--color-red)" : "text-(--color-fg-dim)"} />
      <Item k="CLOSE"   v={`${closeContacts}`} />
      <Item k="T"       v={`${observation.time.toFixed(2)}H`} />
      <Item k="STEP"    v={`${observation.step_count}/${observation.max_steps}`} />
      <Item k="LOC"     v={observation.location.toUpperCase()} />
      <Item k="PREF.Σ"  v={pct(observation.preferences.reduce((a, b) => a + b, 0) / 64, 0)} />
      <span className="mx-4 text-(--color-fg-ghost)">│</span>
    </>
  );

  return (
    <div className="hairline-b relative h-6 overflow-hidden bg-(--color-panel-2)">
      <div className="absolute left-0 top-0 z-10 flex h-full items-center bg-(--color-amber) px-2">
        <span className="text-[10px] font-bold tracking-widest text-black">
          TAPE
        </span>
      </div>
      <div className="pl-14">
        <div className="marquee-track pt-[3px]">
          {items}
          {items}
        </div>
      </div>
    </div>
  );
}
