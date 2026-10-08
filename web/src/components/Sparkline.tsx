// Thirty bars of recent history. This is the densest information on the
// dashboard -- at a glance it tells you not just "is it down" but "has it been
// flapping", which no single number does.
//
// Deliberately not a chart library: it is 30 rects, it must render 100+ times
// per page without thinking about it, and it needs to stay legible at 60px wide.

import { statusColor } from "../lib/status";
import type { CheckStatus } from "../types";

interface Props {
  /** Oldest to newest. Fewer than `slots` renders left-padded with gaps. */
  data: CheckStatus[];
  slots?: number;
  width?: number;
  height?: number;
}

export function Sparkline({
  data,
  slots = 30,
  width = 176,
  height = 26,
}: Props) {
  const gap = 1.5;
  const barWidth = (width - gap * (slots - 1)) / slots;

  // Right-align: the newest check is always the rightmost bar, so a
  // half-empty sparkline still reads "now" at the same place as a full one.
  const padded: (CheckStatus | null)[] = [
    ...Array<null>(Math.max(0, slots - data.length)).fill(null),
    ...data.slice(-slots),
  ];

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Last ${data.length} checks`}
      style={{ display: "block" }}
    >
      {padded.map((status, i) => (
        <rect
          key={i}
          x={i * (barWidth + gap)}
          // Height encodes severity as well as colour: up is short, degraded
          // taller, down full height. A wall of failures should be visibly
          // taller -- that is also what keeps it readable without colour vision.
          y={height - height * barHeight(status)}
          width={barWidth}
          height={height * barHeight(status)}
          rx={1}
          fill={status ? statusColor(status) : "var(--status-empty)"}
        />
      ))}
    </svg>
  );
}

function barHeight(status: CheckStatus | null): number {
  switch (status) {
    case "down":
      return 1;
    case "degraded":
      return 0.72;
    case "up":
      return 0.42;
    default:
      return 0.2;
  }
}
