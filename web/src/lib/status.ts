// The single source of truth for what a status LOOKS like and how it SORTS.
//
// Every screen imports from here. If you find yourself writing
// `status === "down" ? "red" : ...` anywhere else, that logic belongs in this
// file instead -- the moment there are two of them they start disagreeing, and
// the bug shows up as green on one screen and red on another.

import type { CheckStatus, MonitorSummary } from "../types";

/** Higher = more urgent. Drives the default dashboard sort. */
export const SEVERITY: Record<CheckStatus | "unknown", number> = {
  down: 3,
  degraded: 2,
  unknown: 1,
  up: 0,
};

export const STATUS_LABEL: Record<CheckStatus | "unknown", string> = {
  up: "Operational",
  degraded: "Degraded",
  down: "Down",
  unknown: "No data",
};

/**
 * CSS custom property names, not literal colours -- the palette lives in
 * index.css so a restyle is one file. Referenced as
 * `var(${STATUS_COLOR_VAR.down})`.
 */
export const STATUS_COLOR_VAR: Record<CheckStatus | "unknown", string> = {
  up: "--status-up",
  degraded: "--status-degraded",
  down: "--status-down",
  unknown: "--status-unknown",
};

export function statusColor(status: CheckStatus | null | undefined): string {
  return `var(${STATUS_COLOR_VAR[status ?? "unknown"]})`;
}

export function statusLabel(status: CheckStatus | null | undefined): string {
  return STATUS_LABEL[status ?? "unknown"];
}

/**
 * Broken things sort to the top. Down, then degraded, then unknown, then up --
 * name only as a tiebreak.
 *
 * Opening the dashboard should answer "does anything need me?" before you have
 * read a single word, and alphabetical order actively hides the answer.
 */
export function bySeverity(a: MonitorSummary, b: MonitorSummary): number {
  const d = SEVERITY[b.current_status ?? "unknown"] - SEVERITY[a.current_status ?? "unknown"];
  return d !== 0 ? d : a.name.localeCompare(b.name);
}

/** The one-line answer at the top of the page, and on the public status page. */
export function overallStatus(monitors: MonitorSummary[]): CheckStatus | "unknown" {
  if (monitors.length === 0) return "unknown";
  let worst: CheckStatus | "unknown" = "up";
  for (const m of monitors) {
    const s = m.current_status ?? "unknown";
    if (SEVERITY[s] > SEVERITY[worst]) worst = s;
  }
  return worst;
}
