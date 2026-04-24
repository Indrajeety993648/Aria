"use client";

import {
  REWARD_DIMENSIONS,
  type RewardBreakdown,
  type RewardDimension,
} from "@/lib/contracts";

interface RewardRadarProps {
  current: RewardBreakdown | null;
  runningTotal: RewardBreakdown | null;
}

const SIZE = 320;
const CENTER = SIZE / 2;
const RADIUS = 120;
const AXES = REWARD_DIMENSIONS;
const RING_LEVELS = [0.25, 0.5, 0.75, 1.0];
const LABEL_RADIUS = RADIUS + 24;

const AXIS_LABELS: Readonly<Record<RewardDimension, string>> = {
  task_completion: "Task",
  relationship_health: "Relationships",
  user_satisfaction: "Satisfaction",
  time_efficiency: "Efficiency",
  conflict_resolution: "Conflict",
  safety: "Safety",
};

function axisAngle(i: number, n: number): number {
  // Start at top (−90°), clockwise.
  return -Math.PI / 2 + (i * 2 * Math.PI) / n;
}

function point(i: number, n: number, r: number): [number, number] {
  const a = axisAngle(i, n);
  return [CENTER + Math.cos(a) * r, CENTER + Math.sin(a) * r];
}

function normalize(v: number, maxAbs: number): number {
  if (maxAbs <= 0) return 0;
  return Math.max(-1, Math.min(1, v / maxAbs));
}

function polygonPath(
  rb: RewardBreakdown,
  maxAbs: number,
): string {
  const n = AXES.length;
  return AXES.map((dim, i) => {
    const v = normalize(rb[dim], maxAbs);
    const r = Math.max(0, v) * RADIUS;
    const [x, y] = point(i, n, r);
    return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ") + " Z";
}

export function RewardRadar({
  current,
  runningTotal,
}: RewardRadarProps): React.JSX.Element {
  const maxCurrent =
    current === null
      ? 1
      : Math.max(1, ...AXES.map((d) => Math.abs(current[d])));
  const maxTotal =
    runningTotal === null
      ? 1
      : Math.max(1, ...AXES.map((d) => Math.abs(runningTotal[d])));

  return (
    <section className="flex flex-col rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Reward
        </h2>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-sm bg-emerald-400" />
            <span className="text-slate-400">step</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-sm bg-slate-400" />
            <span className="text-slate-400">episode</span>
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-center">
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          width="100%"
          height={SIZE}
          className="max-w-[360px]"
        >
          {/* Rings */}
          {RING_LEVELS.map((lvl) => (
            <polygon
              key={lvl}
              points={AXES.map((_, i) => {
                const [x, y] = point(i, AXES.length, lvl * RADIUS);
                return `${x},${y}`;
              }).join(" ")}
              fill="none"
              stroke="#1e293b"
              strokeWidth={1}
            />
          ))}

          {/* Axes */}
          {AXES.map((_, i) => {
            const [x, y] = point(i, AXES.length, RADIUS);
            return (
              <line
                key={i}
                x1={CENTER}
                y1={CENTER}
                x2={x}
                y2={y}
                stroke="#1e293b"
                strokeWidth={1}
              />
            );
          })}

          {/* Episode total (behind) */}
          {runningTotal !== null ? (
            <path
              d={polygonPath(runningTotal, maxTotal)}
              fill="rgba(148,163,184,0.18)"
              stroke="rgba(148,163,184,0.7)"
              strokeWidth={1.5}
            />
          ) : null}

          {/* Current step (front) */}
          {current !== null ? (
            <path
              d={polygonPath(current, maxCurrent)}
              fill="rgba(52,211,153,0.25)"
              stroke="#34d399"
              strokeWidth={2}
            />
          ) : null}

          {/* Dots on current */}
          {current !== null
            ? AXES.map((dim, i) => {
                const v = normalize(current[dim], maxCurrent);
                const r = Math.max(0, v) * RADIUS;
                const [x, y] = point(i, AXES.length, r);
                return (
                  <circle
                    key={dim}
                    cx={x}
                    cy={y}
                    r={3}
                    fill="#34d399"
                  />
                );
              })
            : null}

          {/* Labels */}
          {AXES.map((dim, i) => {
            const [x, y] = point(i, AXES.length, LABEL_RADIUS);
            const a = axisAngle(i, AXES.length);
            let anchor: "start" | "middle" | "end" = "middle";
            if (Math.cos(a) > 0.2) anchor = "start";
            else if (Math.cos(a) < -0.2) anchor = "end";
            return (
              <text
                key={dim}
                x={x}
                y={y}
                fill="#94a3b8"
                fontSize={11}
                textAnchor={anchor}
                dominantBaseline="middle"
              >
                {AXIS_LABELS[dim]}
              </text>
            );
          })}
        </svg>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        {AXES.map((dim) => (
          <div
            key={dim}
            className="flex items-center justify-between border-b border-slate-800/60 py-1"
          >
            <dt className="text-slate-400">{AXIS_LABELS[dim]}</dt>
            <dd className="tabular-nums text-slate-200">
              {current !== null ? current[dim].toFixed(2) : "—"}
            </dd>
          </div>
        ))}
        <div className="col-span-2 flex items-center justify-between pt-2 text-sm">
          <dt className="font-semibold text-slate-300">Total (step)</dt>
          <dd className="tabular-nums font-semibold text-emerald-300">
            {current !== null ? current.total.toFixed(3) : "—"}
          </dd>
        </div>
      </dl>
    </section>
  );
}
