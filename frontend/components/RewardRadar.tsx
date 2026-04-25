"use client";

import {
  REWARD_DIMENSIONS,
  type RewardBreakdown,
  type RewardDimension,
} from "@/lib/contracts";
import { sign } from "@/lib/format";
import { Panel } from "./Panel";

interface RewardRadarProps {
  step: RewardBreakdown;
  running: RewardBreakdown;
}

const LABEL: Record<RewardDimension, string> = {
  task_completion: "TASK",
  relationship_health: "REL",
  user_satisfaction: "SAT",
  time_efficiency: "TIME",
  conflict_resolution: "CONF",
  safety: "SAFE",
};

const W = 300;
const H = 300;
const CX = W / 2;
const CY = H / 2 + 4;
const RADIUS = 100;
const AXES = REWARD_DIMENSIONS.length;

function polar(i: number, r: number): [number, number] {
  const a = (Math.PI * 2 * i) / AXES - Math.PI / 2;
  return [CX + Math.cos(a) * r, CY + Math.sin(a) * r];
}

function polygonPoints(vals: number[], normMax: number): string {
  return vals
    .map((v, i) => {
      const clamped = Math.max(-1, Math.min(1, v / normMax));
      const [x, y] = polar(i, RADIUS * ((clamped + 1) / 2));
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function RewardRadar({ step, running }: RewardRadarProps) {
  const stepVals = REWARD_DIMENSIONS.map((d) => step[d]);
  const runVals = REWARD_DIMENSIONS.map((d) => running[d]);
  const runNormMax = Math.max(1, ...runVals.map((v) => Math.abs(v))) || 1;

  const ringVals = [0.25, 0.5, 0.75, 1.0];

  return (
    <Panel
      label="REWARD // 6D"
      meta={
        <span className="flex items-center gap-3 tracking-widest">
          <span>
            <span className="text-(--color-fg-muted) mr-1">Σ</span>
            <span className="data text-(--color-phosphor)">
              {sign(running.total, 2)}
            </span>
          </span>
          <span>
            <span className="text-(--color-fg-muted) mr-1">Δ</span>
            <span
              className={`data ${
                step.total >= 0
                  ? "text-(--color-phosphor)"
                  : "text-(--color-red)"
              }`}
            >
              {sign(step.total, 3)}
            </span>
          </span>
        </span>
      }
      stateDot={step.total >= 0 ? "live" : "warn"}
      className="h-full"
    >
      <div className="flex h-full flex-col items-center justify-between gap-2 p-3">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full max-w-[320px]"
          aria-label="reward radar"
        >
          {/* concentric rings */}
          {ringVals.map((v) => (
            <polygon
              key={v}
              points={Array.from({ length: AXES })
                .map((_, i) => polar(i, RADIUS * v).join(","))
                .join(" ")}
              fill="none"
              stroke="#1a1a1a"
              strokeWidth={1}
            />
          ))}
          {/* axis spokes */}
          {REWARD_DIMENSIONS.map((_, i) => {
            const [x, y] = polar(i, RADIUS);
            return (
              <line
                key={i}
                x1={CX}
                y1={CY}
                x2={x}
                y2={y}
                stroke="#1a1a1a"
                strokeWidth={1}
              />
            );
          })}
          {/* zero-center ring (50%) slightly brighter */}
          <polygon
            points={Array.from({ length: AXES })
              .map((_, i) => polar(i, RADIUS * 0.5).join(","))
              .join(" ")}
            fill="none"
            stroke="#2a2a2a"
            strokeWidth={1}
          />

          {/* running (amber, dim fill) */}
          <polygon
            points={polygonPoints(runVals, runNormMax)}
            fill="#ff9e1f"
            fillOpacity={0.1}
            stroke="#ff9e1f"
            strokeWidth={1.2}
            strokeDasharray="3 2"
          />

          {/* current step (phosphor) */}
          <polygon
            points={polygonPoints(stepVals, 1.0)}
            fill="#39ff14"
            fillOpacity={0.12}
            stroke="#39ff14"
            strokeWidth={1.6}
          />

          {/* axis labels */}
          {REWARD_DIMENSIONS.map((dim, i) => {
            const [x, y] = polar(i, RADIUS + 18);
            return (
              <text
                key={dim}
                x={x}
                y={y}
                fill="#9b9790"
                fontSize={10}
                fontFamily="var(--font-mono)"
                textAnchor="middle"
                dominantBaseline="middle"
                letterSpacing="0.14em"
              >
                {LABEL[dim]}
              </text>
            );
          })}
        </svg>

        {/* per-dim rail */}
        <div className="grid w-full grid-cols-6 gap-1 text-[10px] tracking-widest">
          {REWARD_DIMENSIONS.map((d) => {
            const v = step[d];
            const positive = v >= 0;
            return (
              <div
                key={d}
                className="flex flex-col items-center border border-(--color-border) bg-(--color-panel-2) py-1"
              >
                <span className="text-(--color-fg-muted)">{LABEL[d]}</span>
                <span
                  className={`data ${
                    positive
                      ? "text-(--color-phosphor)"
                      : "text-(--color-red)"
                  }`}
                >
                  {sign(v, 2)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </Panel>
  );
}
