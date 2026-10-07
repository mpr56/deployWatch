// The atom of the whole product.
//
// The sparkline, status dot and metric layout here get reused on the monitor
// detail screen and (in a different visual language) on the public status page.
// Get this right and the rest composes from it.
//
// Bone structure only -- classNames are hooks for your own visual treatment.

import { Link } from "react-router-dom";

import { ms, relativeTime, uptime } from "../lib/format";
import { statusLabel } from "../lib/status";
import type { MonitorSummary } from "../types";
import { Sparkline } from "./Sparkline";
import { StatusDot } from "./StatusDot";

export function MonitorRow({ monitor }: { monitor: MonitorSummary }) {
  const status = monitor.current_status;

  return (
    <Link
      to={`/monitors/${monitor.id}`}
      className={`row row--${status ?? "unknown"}`}
    >
      <div className="row__status">
        <StatusDot status={status} />
      </div>

      <div className="row__identity">
        <div className="row__name">{monitor.name}</div>
        <div className="row__url">{monitor.url}</div>
      </div>

      <div className="row__spark">
        <Sparkline data={monitor.sparkline} />
      </div>

      <div className="row__metric">
        <div className="row__metric-value">
          {ms(monitor.last_response_time_ms)}
        </div>
        <div className="row__metric-label">response</div>
      </div>

      <div className="row__metric">
        <div className="row__metric-value">{uptime(monitor.uptime_24h)}</div>
        <div className="row__metric-label">24h uptime</div>
      </div>

      <div className="row__meta">
        <div className="row__state">{statusLabel(status)}</div>
        <div className="row__checked">{relativeTime(monitor.last_checked_at)}</div>
      </div>
    </Link>
  );
}
