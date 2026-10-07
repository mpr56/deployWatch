export function ms(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

/**
 * Uptime needs more precision the closer it gets to 100 -- the difference
 * between 99.9% and 99.99% is eight hours a year, and rounding both to "100%"
 * throws away the only number anyone actually cares about.
 */
export function uptime(pct: number | null | undefined): string {
  if (pct == null) return "—";
  if (pct === 100) return "100%";
  if (pct > 99.9) return `${pct.toFixed(3)}%`;
  if (pct > 99) return `${pct.toFixed(2)}%`;
  return `${pct.toFixed(1)}%`;
}

export function duration(secs: number | null | undefined): string {
  if (secs == null) return "—";
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  const h = Math.floor(secs / 3600);
  return `${h}h ${Math.floor((secs % 3600) / 60)}m`;
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const secs = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}
