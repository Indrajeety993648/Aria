/**
 * Display formatters used across the terminal. All are pure.
 * Tabular-nums are enforced at the CSS level; these helpers just
 * pad and sign.
 */

export const pad = (n: number, w: number): string =>
  String(n).padStart(w, "0");

export const sign = (n: number, digits = 3): string => {
  const s = n >= 0 ? "+" : "-";
  return `${s}${Math.abs(n).toFixed(digits)}`;
};

export const pct = (n: number, digits = 1): string =>
  `${(n * 100).toFixed(digits)}%`;

export const clock = (d: Date = new Date()): string =>
  `${pad(d.getUTCHours(), 2)}:${pad(d.getUTCMinutes(), 2)}:${pad(d.getUTCSeconds(), 2)}Z`;

export const hhmm = (hour: number): string => {
  const h = Math.floor(hour);
  const m = Math.round((hour - h) * 60);
  return `${pad(h, 2)}:${pad(m, 2)}`;
};

export const dayLabel = (offset: number): string => {
  if (offset === 0) return "TODAY";
  if (offset === 1) return "TOMRW";
  return `D+${pad(offset, 2)}`;
};

export const truncate = (s: string, n: number): string =>
  s.length <= n ? s : s.slice(0, n - 1) + "…";

export const upperShort = (s: string, n = 12): string =>
  truncate(s.replace(/_/g, " ").toUpperCase(), n);

export const formatSession = (id: string): string =>
  id.slice(0, 8).toUpperCase();
