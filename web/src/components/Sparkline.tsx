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
  width = 120,
  height = 28,
}: Props) {
  const gap = 1;
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
          // Degraded and down bars are full height; up bars are shorter. A wall
          // of failures should be visibly taller, not just differently coloured
          // -- that is also what makes this readable without colour vision.
          y={status === "up" ? height * 0.45 : 0}
          width={barWidth}
          height={status === "up" ? height * 0.55 : height}
          rx={1}
          fill={status ? statusColor(status) : "var(--status-empty)"}
        />
      ))}
    </svg>
  );
}
