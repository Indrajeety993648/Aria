"use client";

import type {
  AriaObservation,
  CalendarEvent,
  InboxItem,
  PendingTask,
  RelationshipNode,
} from "@/lib/contracts";

interface EnvInspectorProps {
  observation: AriaObservation | null;
}

const DAY_NAMES = ["Today", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatHour(h: number): string {
  const hh = Math.floor(h);
  const mm = Math.round((h - hh) * 60);
  const pad = (n: number): string => (n < 10 ? `0${n}` : `${n}`);
  return `${pad(hh)}:${pad(mm)}`;
}

function urgencyClass(u: number): string {
  if (u >= 0.8) return "bg-red-500/15 text-red-300 border-red-500/30";
  if (u >= 0.5) return "bg-amber-500/15 text-amber-300 border-amber-500/30";
  return "bg-slate-700/30 text-slate-400 border-slate-600/30";
}

function CalendarSection({
  events,
}: {
  events: CalendarEvent[];
}): React.JSX.Element {
  const next7: CalendarEvent[] = events.filter((e) => e.day_offset < 7);
  const byDay = new Map<number, CalendarEvent[]>();
  for (const e of next7) {
    const list = byDay.get(e.day_offset) ?? [];
    list.push(e);
    byDay.set(e.day_offset, list);
  }
  const days = Array.from({ length: 7 }, (_, i) => i);

  return (
    <div>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Calendar (next 7 days)
      </h3>
      <div className="grid grid-cols-7 gap-1.5">
        {days.map((d) => {
          const items = (byDay.get(d) ?? []).slice().sort(
            (a, b) => a.start_hour - b.start_hour,
          );
          return (
            <div
              key={d}
              className="min-h-[96px] rounded-lg border border-slate-800 bg-slate-950/40 p-1.5"
            >
              <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">
                {DAY_NAMES[d] ?? `+${d}`}
              </div>
              <div className="flex flex-col gap-1">
                {items.map((e) => (
                  <div
                    key={e.event_id}
                    className="rounded border border-emerald-500/20 bg-emerald-500/5 px-1.5 py-1 text-[10px] leading-tight text-slate-200"
                    title={e.title}
                  >
                    <div className="text-emerald-300/80">
                      {formatHour(e.start_hour)}
                    </div>
                    <div className="truncate">{e.title}</div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function InboxSection({
  items,
}: {
  items: InboxItem[];
}): React.JSX.Element {
  const top = items.slice(0, 10);
  return (
    <div>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Inbox (top 10)
      </h3>
      <ul className="flex flex-col divide-y divide-slate-800/60 rounded-lg border border-slate-800 bg-slate-950/40">
        {top.map((i) => (
          <li
            key={i.email_id}
            className="flex items-center gap-3 px-3 py-2 text-sm"
          >
            <span
              className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${urgencyClass(i.urgency)}`}
            >
              {i.urgency >= 0.8
                ? "urgent"
                : i.urgency >= 0.5
                  ? "normal"
                  : "low"}
            </span>
            <span className="w-24 shrink-0 truncate text-xs text-slate-400">
              {i.sender_id}
            </span>
            <span className="min-w-0 flex-1 truncate text-slate-200">
              {i.subject}
            </span>
            <span className="shrink-0 text-xs text-slate-500">
              {i.age_hours.toFixed(0)}h
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RelationshipsSection({
  relationships,
}: {
  relationships: RelationshipNode[];
}): React.JSX.Element {
  return (
    <div>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Relationships
      </h3>
      <ul className="flex flex-col gap-1.5">
        {relationships.map((r) => (
          <li
            key={r.contact_id}
            className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2"
          >
            <div className="w-32 shrink-0">
              <div className="truncate text-sm text-slate-200">{r.name}</div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">
                {r.relationship_kind}
              </div>
            </div>
            <div className="flex-1">
              <div className="relative h-2 overflow-hidden rounded-full bg-slate-800">
                <div
                  className="absolute inset-y-0 left-0 bg-emerald-400/70"
                  style={{
                    width: `${Math.round(r.closeness * 100)}%`,
                  }}
                />
              </div>
            </div>
            <div className="w-10 shrink-0 text-right text-xs tabular-nums text-slate-400">
              {r.closeness.toFixed(2)}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TasksSection({
  tasks,
}: {
  tasks: PendingTask[];
}): React.JSX.Element {
  return (
    <div>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Pending tasks
      </h3>
      <ul className="flex flex-col gap-1.5">
        {tasks.map((t) => {
          const overdue = t.deadline_hours < 0;
          return (
            <li
              key={t.task_id}
              className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm"
            >
              <span
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${t.status === "done" ? "border-emerald-400 bg-emerald-500/20" : "border-slate-600"}`}
              >
                {t.status === "done" ? (
                  <svg
                    viewBox="0 0 16 16"
                    className="h-3 w-3 text-emerald-300"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M3 8l3 3 7-7" />
                  </svg>
                ) : null}
              </span>
              <span className="min-w-0 flex-1 truncate text-slate-200">
                {t.title}
              </span>
              <span
                className={`shrink-0 text-xs tabular-nums ${overdue ? "text-red-400" : "text-slate-400"}`}
              >
                {overdue
                  ? `${Math.abs(t.deadline_hours).toFixed(0)}h overdue`
                  : `${t.deadline_hours.toFixed(0)}h left`}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function EnvInspector({
  observation,
}: EnvInspectorProps): React.JSX.Element {
  if (observation === null) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Environment
        </h2>
        <p className="mt-4 text-sm text-slate-500">
          Waiting for observation...
        </p>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Environment
        </h2>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span>
            scenario:{" "}
            <span className="text-slate-300">
              {observation.scenario_category ?? "—"}
            </span>
          </span>
          <span>
            step:{" "}
            <span className="text-slate-300">
              {observation.step_count}/{observation.max_steps}
            </span>
          </span>
          <span>
            time:{" "}
            <span className="text-slate-300">
              {formatHour(observation.time)}
            </span>
          </span>
        </div>
      </div>
      <CalendarSection events={observation.calendar} />
      <InboxSection items={observation.inbox} />
      <RelationshipsSection relationships={observation.relationships} />
      <TasksSection tasks={observation.pending_tasks} />
    </section>
  );
}
