// One incident: what broke, for how long, and the timeline of checks from the
// first failure to recovery. Consecutive identical checks collapse into one
// line, so a change of error mid-incident (timeout -> 502 -> timeout) stands
// out -- that is often the most diagnostic thing on the screen.

import { Link, useParams } from "react-router-dom";

import { StatusDot } from "../components/StatusDot";
import { useIncident, useIncidentChecks, useMonitor } from "../lib/api";
import { duration, ms } from "../lib/format";
import { statusColor, statusLabel } from "../lib/status";
import type { Check, CheckStatus } from "../types";

interface Run {
  status: CheckStatus;
  error: string | null;
  from: string;
  to: string;
  count: number;
  avgMs: number | null;
}

function toRuns(checks: Check[]): Run[] {
  const runs: Run[] = [];
  for (const c of checks) {
    const last = runs[runs.length - 1];
    if (last && last.status === c.status && last.error === c.error_message) {
      last.to = c.checked_at;
      last.count += 1;
      if (c.response_time_ms != null) {
        last.avgMs =
          last.avgMs == null
            ? c.response_time_ms
            : (last.avgMs * (last.count - 1) + c.response_time_ms) / last.count;
      }
    } else {
      runs.push({
        status: c.status,
        error: c.error_message,
        from: c.checked_at,
        to: c.checked_at,
        count: 1,
        avgMs: c.response_time_ms,
      });
    }
  }
  return runs;
}

const time = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export function IncidentDetail() {
  const id = Number(useParams().id);
  const incident = useIncident(id);
  const checks = useIncidentChecks(id);
  const monitor = useMonitor(incident.data?.monitor_id ?? 0);

  if (incident.isLoading) return <div className="page">Loading…</div>;
  if (!incident.data) return <div className="page error">Incident not found</div>;

  const inc = incident.data;
  const open = inc.resolved_at === null;
  const elapsed = open
    ? Math.round((Date.now() - new Date(inc.started_at).getTime()) / 1000)
    : inc.duration_secs;
  const runs = toRuns(checks.data ?? []);

  return (
    <div className="page page--narrow">
      <header className="page__head">
        <div>
          <h1 style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <StatusDot status={open ? "down" : "up"} size={10} halo />
            {monitor.data?.name ?? "Monitor"} {open ? "is down" : "was down"}
          </h1>
          <p className="page__sub">
            {inc.cause ?? "Unknown cause"} ·{" "}
            {monitor.data && (
              <Link to={`/monitors/${monitor.data.id}`}>{monitor.data.url}</Link>
            )}
          </p>
        </div>
        <span
          className="pill"
          style={{ color: statusColor(open ? "down" : "up") }}
        >
          {open ? "Ongoing" : "Resolved"}
        </span>
      </header>

      <div className="stats stats--3">
        <div className="stat">
          <div className="stat__label">{open ? "Down for" : "Duration"}</div>
          <div className="stat__value">{duration(elapsed)}</div>
        </div>
        <div className="stat">
          <div className="stat__label">Failed checks</div>
          <div className="stat__value">{inc.checks_failed}</div>
        </div>
        <div className="stat">
          <div className="stat__label">Started</div>
          <div className="stat__value stat__value--sm">
            {new Date(inc.started_at).toLocaleString()}
          </div>
        </div>
      </div>

      <section className="panel">
        <h2>Timeline</h2>
        <ol className="timeline">
          {runs.map((r, i) => (
            <li key={i} className="timeline__item">
              <span
                className="timeline__marker"
                style={{ background: statusColor(r.status) }}
              />
              <div className="timeline__time">
                {time(r.from)}
                {r.count > 1 && ` – ${time(r.to)}`}
              </div>
              <div className="timeline__body">
                <span style={{ color: statusColor(r.status), fontWeight: 600 }}>
                  {i === 0 ? "First failure" : r.status === "down" ? "Down" : statusLabel(r.status)}
                </span>
                {r.error && <span className="timeline__err">{r.error}</span>}
                {r.avgMs != null && <span className="muted">{ms(r.avgMs)}</span>}
                <span className="muted">
                  {r.count} check{r.count === 1 ? "" : "s"}
                </span>
              </div>
            </li>
          ))}
          {!open && inc.resolved_at && (
            <li className="timeline__item">
              <span
                className="timeline__marker"
                style={{ background: statusColor("up") }}
              />
              <div className="timeline__time">{time(inc.resolved_at)}</div>
              <div className="timeline__body">
                <span style={{ color: statusColor("up"), fontWeight: 600 }}>
                  Resolved
                </span>
                <span className="muted">after {duration(inc.duration_secs)}</span>
              </div>
            </li>
          )}
          {runs.length === 0 && <p className="muted">No checks recorded.</p>}
        </ol>
      </section>
    </div>
  );
}
