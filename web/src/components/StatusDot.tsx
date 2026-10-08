import { statusColor, statusLabel } from "../lib/status";
import type { CheckStatus } from "../types";

interface Props {
  status: CheckStatus | null | undefined;
  size?: number;
  /** Down monitors pulse. Nothing else does -- if everything moves, nothing does. */
  pulse?: boolean;
  /** Soft ring in the status tint, as used on dashboard rows. */
  halo?: boolean;
}

export function StatusDot({ status, size = 10, pulse = true, halo = false }: Props) {
  const animate = pulse && status === "down";
  const classes = ["dot"];
  if (animate) classes.push("dot--pulse");
  if (halo && status) classes.push(`dot--halo-${status}`);
  return (
    <span
      className={classes.join(" ")}
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
