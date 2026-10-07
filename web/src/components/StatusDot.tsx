import { statusColor, statusLabel } from "../lib/status";
import type { CheckStatus } from "../types";

interface Props {
  status: CheckStatus | null | undefined;
  size?: number;
  /** Down monitors pulse. Nothing else does -- if everything moves, nothing does. */
  pulse?: boolean;
}

export function StatusDot({ status, size = 10, pulse = true }: Props) {
  const animate = pulse && status === "down";
  return (
    <span
      className={animate ? "dot dot--pulse" : "dot"}
      style={{
        width: size,
        height: size,
        background: statusColor(status),
      }}
      role="img"
      aria-label={statusLabel(status)}
      title={statusLabel(status)}
    />
  );
}
