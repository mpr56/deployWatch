// The atom of the whole product: one monitor, one line.
//
// Dot + name + URL, last response, 24h uptime, then the last 30 checks as
// bars. Broken rows get a tinted background and a coloured left edge so they
// read from across the room before you read a word.

import { Link } from "react-router-dom";

import { useDeleteMonitor } from "../lib/api";
import { confirmDelete } from "../lib/confirm";
import { ms, uptime } from "../lib/format";
import { sslWarning } from "../lib/ssl";
import { statusColor } from "../lib/status";
import type { MonitorSummary } from "../types";
import { Sparkline } from "./Sparkline";
import { StatusDot } from "./StatusDot";

export function MonitorRow({ monitor }: { monitor: MonitorSummary }) {
  const status = monitor.current_status;
  const del = useDeleteMonitor();

  const onDelete = (e: React.MouseEvent) => {
    // The whole row is a link; keep the click from navigating.
    e.preventDefault();
    e.stopPropagation();
    if (confirmDelete(monitor.name)) {
      del.mutate(monitor.id);
    }
  };

  const ssl = sslWarning(monitor.ssl_expires_at, monitor.ssl_error);

  const resp =
    status === "down" && monitor.last_response_time_ms == null
      ? "failed"
      : ms(monitor.last_response_time_ms);

  return (
    <Link
      to={`/monitors/${monitor.id}`}
      className={`row row--${status ?? "unknown"}`}
    >
      <div className="row__identity">
        <StatusDot status={status} size={8} halo />
        <div className="row__text">
          <div className="row__name">
            {monitor.name}
            {ssl && <span className="ssl-badge">{ssl}</span>}
          </div>
          <div className="row__url">{monitor.url.replace(/^https?:\/\//, "")}</div>
        </div>
      </div>

      <div
        className="row__resp"
        style={{ color: status && status !== "up" ? statusColor(status) : undefined }}
      >
        {resp}
      </div>

      <div className="row__uptime">{uptime(monitor.uptime_24h)}</div>

      <div className="row__spark">
        <Sparkline data={monitor.sparkline} />
      </div>

      <div className="row__actions">
        <button
          className="btn btn--sm btn--danger"
          onClick={onDelete}
          disabled={del.isPending}
          aria-label={`Delete ${monitor.name}`}
        >
          Delete
        </button>
      </div>
    </Link>
  );
}
