"use client";

import { useEffect, useRef } from "react";

export type OrbState = "idle" | "listening" | "wake" | "speaking" | "muted";

interface VoiceOrbProps {
  state: OrbState;
  analyser: AnalyserNode | null;
  className?: string;
}

/**
 * Pure-canvas voice-assistant logo.
 *
 * Composed layers (painted back-to-front):
 *   1. Ambient radial glow
 *   2. Outer dashed ring (slow rotation via lineDashOffset)
 *   3. JARVIS-style tick marks (every 9th emphasised)
 *   4. Three orbital arc segments (different radii, speeds, directions)
 *   5. Circular audio waveform (FFT displaces points outward, 180 samples)
 *   6. Soft core glow
 *   7. Pulsing center dot
 *   8. Radiating rays (speaking / wake only)
 *
 * Everything is state-driven. Colors shift phosphor → cyan → amber → red;
 * rotation + wave amplitude + ray emission all accelerate with activity.
 * No external assets, no media element, no network — always visible.
 */

type Palette = {
  core: [number, number, number];
  accent: [number, number, number];
  glow: [number, number, number];
  dim: [number, number, number];
};

const PALETTES: Record<OrbState, Palette> = {
  idle:      { core: [57, 255, 20],  accent: [123, 255, 92],  glow: [57, 255, 20],  dim: [31, 138, 10] },
  listening: { core: [57, 255, 20],  accent: [123, 255, 92],  glow: [57, 255, 20],  dim: [31, 138, 10] },
  wake:      { core: [0, 212, 255],  accent: [102, 229, 255], glow: [0, 212, 255],  dim: [10, 107, 138] },
  speaking:  { core: [255, 158, 31], accent: [255, 185, 92],  glow: [255, 158, 31], dim: [138, 90, 18] },
  muted:     { core: [255, 59, 48],  accent: [255, 107, 99],  glow: [255, 59, 48],  dim: [107, 24, 21] },
};

const rgba = (c: [number, number, number], a: number) =>
  `rgba(${c[0]},${c[1]},${c[2]},${a})`;

export function VoiceOrb({ state, analyser, className = "" }: VoiceOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const DPR = window.devicePixelRatio || 1;
    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      canvas.width = Math.floor(rect.width * DPR);
      canvas.height = Math.floor(rect.height * DPR);
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const fft = analyser
      ? new Uint8Array(analyser.frequencyBinCount)
      : new Uint8Array(128);

    const startTs = performance.now();
    let raf = 0;

    const render = () => {
      const w = canvas.width / DPR;
      const h = canvas.height / DPR;
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.min(w, h) * 0.42;
      const t = (performance.now() - startTs) / 1000;

      ctx.clearRect(0, 0, w, h);

      const p = PALETTES[state];
      const active = state !== "idle" && state !== "muted";
      const intensity =
        state === "speaking" ? 1.0 :
        state === "wake"     ? 0.9 :
        state === "listening"? 0.65 :
        state === "muted"    ? 0.25 :
        0.42;
      const speedMul =
        state === "speaking" ? 2.4 :
        state === "wake"     ? 1.8 :
        state === "listening"? 1.1 :
        state === "muted"    ? 0.0 :
        0.6;

      // pull audio or synthesize a breathing pattern
      if (analyser && active) analyser.getByteFrequencyData(fft);
      else {
        for (let i = 0; i < fft.length; i++) {
          const phase = (i / fft.length) * Math.PI * 2;
          const v =
            24 +
            Math.sin(t * 1.3 + phase) * 18 +
            Math.sin(t * 0.6 + phase * 2.7) * 12;
          fft[i] = Math.max(0, Math.min(255, Math.floor(v)));
        }
      }

      // mean of low band → drives breathing scale
      let sum = 0;
      for (let i = 0; i < 32; i++) sum += fft[i];
      const meanAmp = sum / 32 / 255;
      const breath = 0.5 + 0.5 * Math.sin(t * 1.3);
      const scale = 1 + (active ? meanAmp * 0.09 : breath * 0.04);

      ctx.save();
      ctx.translate(cx, cy);
      ctx.scale(scale, scale);

      // 1. AMBIENT GLOW ---------------------------------------------------
      const glowR = R * 1.85;
      const glowGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, glowR);
      glowGrad.addColorStop(0, rgba(p.glow, 0.34 * intensity));
      glowGrad.addColorStop(0.32, rgba(p.glow, 0.13 * intensity));
      glowGrad.addColorStop(0.72, rgba(p.glow, 0.04 * intensity));
      glowGrad.addColorStop(1, rgba(p.glow, 0));
      ctx.fillStyle = glowGrad;
      ctx.fillRect(-glowR, -glowR, glowR * 2, glowR * 2);

      // 2. OUTER DASHED RING ---------------------------------------------
      ctx.strokeStyle = rgba(p.dim, 0.7);
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 3]);
      ctx.lineDashOffset = -t * 10 * speedMul;
      ctx.beginPath();
      ctx.arc(0, 0, R, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // 3. TICK MARKS ----------------------------------------------------
      ctx.strokeStyle = rgba(p.glow, 0.22 * intensity);
      ctx.lineWidth = 1;
      const tickCount = 72;
      const tickRotate = t * 0.08 * speedMul;
      for (let i = 0; i < tickCount; i++) {
        const a = (i / tickCount) * Math.PI * 2 + tickRotate;
        const inner = R * 0.93;
        const outer = R * (i % 9 === 0 ? 1.0 : 0.965);
        ctx.beginPath();
        ctx.moveTo(Math.cos(a) * inner, Math.sin(a) * inner);
        ctx.lineTo(Math.cos(a) * outer, Math.sin(a) * outer);
        ctx.stroke();
      }

      // 4. ORBITAL ARC SEGMENTS ------------------------------------------
      const arcs = [
        { r: R * 0.84, base: 0.30, len: 0.22, width: 2.0, dir:  1 },
        { r: R * 0.72, base: 0.55, len: 0.16, width: 1.5, dir: -1 },
        { r: R * 0.58, base: 0.90, len: 0.12, width: 1.2, dir:  1 },
      ];
      ctx.lineCap = "round";
      for (const arc of arcs) {
        const start = arc.base + t * arc.dir * speedMul * 0.35;
        const startA = start * Math.PI * 2;
        const endA = startA + arc.len * Math.PI * 2;
        ctx.strokeStyle = rgba(p.accent, 0.75 * intensity);
        ctx.shadowColor = rgba(p.glow, 0.6 * intensity);
        ctx.shadowBlur = 6;
        ctx.lineWidth = arc.width;
        ctx.beginPath();
        ctx.arc(0, 0, arc.r, startA, endA);
        ctx.stroke();
      }
      ctx.shadowBlur = 0;
      ctx.lineCap = "butt";

      // 5. CIRCULAR AUDIO WAVEFORM ---------------------------------------
      const waveR = R * 0.62;
      const points = 180;
      ctx.beginPath();
      for (let i = 0; i <= points; i++) {
        const a = (i / points) * Math.PI * 2 - Math.PI / 2;
        const bin = Math.floor(
          (i <= points / 2 ? i : points - i) / (points / 2) * 64,
        );
        const v = fft[Math.min(fft.length - 1, bin)] / 255;
        const displace = v * R * 0.26 * (active ? 1 : 0.5);
        const rr = waveR + displace;
        const x = Math.cos(a) * rr;
        const y = Math.sin(a) * rr;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = rgba(p.accent, 0.9 * intensity);
      ctx.lineWidth = 1.6;
      ctx.shadowColor = rgba(p.glow, 0.85 * intensity);
      ctx.shadowBlur = 10;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // 6. CORE GLOW + 7. CENTER DOT -------------------------------------
      const coreR = R * 0.32 * (0.9 + breath * 0.12 + meanAmp * 0.18);
      const coreGrad = ctx.createRadialGradient(0, 0, 0, 0, 0, coreR);
      coreGrad.addColorStop(0, rgba(p.core, 0.95 * intensity));
      coreGrad.addColorStop(0.45, rgba(p.core, 0.35 * intensity));
      coreGrad.addColorStop(1, rgba(p.core, 0));
      ctx.fillStyle = coreGrad;
      ctx.beginPath();
      ctx.arc(0, 0, coreR, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = rgba(p.core, intensity);
      ctx.shadowColor = rgba(p.core, 1);
      ctx.shadowBlur = 18 * intensity;
      ctx.beginPath();
      ctx.arc(0, 0, 4 + breath * 1.6, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // 8. RADIATING RAYS (speaking / wake) -------------------------------
      if (state === "speaking" || state === "wake") {
        const rays = 6;
        const period = state === "speaking" ? 1.2 : 1.8;
        for (let k = 0; k < 2; k++) {
          const rayT = ((t / period) + k * 0.5) % 1;
          for (let i = 0; i < rays; i++) {
            const a = (i / rays) * Math.PI * 2 + t * 0.2;
            const inner = R * 0.3 + rayT * R * 0.55;
            const outer = inner + R * 0.16;
            const alpha = (1 - rayT) * 0.7 * intensity;
            ctx.strokeStyle = rgba(p.accent, alpha);
            ctx.shadowColor = rgba(p.glow, alpha);
            ctx.shadowBlur = 8;
            ctx.lineWidth = 2;
            ctx.lineCap = "round";
            ctx.beginPath();
            ctx.moveTo(Math.cos(a) * inner, Math.sin(a) * inner);
            ctx.lineTo(Math.cos(a) * outer, Math.sin(a) * outer);
            ctx.stroke();
          }
        }
        ctx.shadowBlur = 0;
        ctx.lineCap = "butt";
      }

      ctx.restore();

      raf = requestAnimationFrame(render);
    };
    render();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [analyser, state]);

  // Use the state color as a soft CSS fallback glow so even before the
  // canvas mounts (or if JS fails entirely) there's something on screen.
  const palette = PALETTES[state];
  const cssGlow = `radial-gradient(ellipse at center, rgba(${palette.glow[0]},${palette.glow[1]},${palette.glow[2]},0.22) 0%, rgba(0,0,0,1) 78%)`;

  // IMPORTANT: inline styles for positioning. Tailwind v4's `relative` and
  // `absolute` belong to the same utility group and their precedence depends
  // on generated CSS order — not className string order. Inline > utility,
  // so this is unambiguous.
  return (
    <div
      className={`overflow-hidden bg-black ${className}`}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: cssGlow,
          transition: "background 400ms ease-out",
        }}
        aria-hidden
      />
      <canvas
        ref={canvasRef}
        aria-label="ARIA voice assistant state indicator"
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          display: "block",
        }}
      />
    </div>
  );
}
