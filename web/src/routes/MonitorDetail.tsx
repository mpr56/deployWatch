// One monitor, expanded. Percentile stats, response time chart, recent checks,
// incident history.
//
// The recent-checks table is wired up because /api/checks works. The chart and
// the percentile row need endpoints you have not written yet -- see
// api/app/routers/checks.py.

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { StatusDot } from "../components/StatusDot";
import { confirmDelete } from "../lib/confirm";
import { useChecks, useDeleteMonitor, useIncidents, useMonitor } from "../lib/api";
import { duration, ms, relativeTime } from "../lib/format";
import type { TimeRange } from "../types";

const RANGES: TimeRange[] = ["1h", "24h", "7d", "30d"];

export function MonitorDetail() {
  const id = Number(useParams().id);
  const [range, setRange] = useState<TimeRange>("24h");

  const monitor = useMonitor(id);
  const checks = useChecks(id, range);
  const incidents = useIncidents(id);
  const del = useDeleteMonitor();
  const navigate = useNavigate();

  if (monitor.isLoading) return <div className="page">Loading…</div>;
  if (!monitor.data) return <div className="page error">Not found</div>;

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <h1>{monitor.data.name}</h1>
          <p className="page__sub">
            <a href={monitor.data.url} target="_blank" rel="noreferrer">
              {monitor.data.url}
            </a>{" "}
            · every {monitor.data.interval_secs}s · expects{" "}
            {monitor.data.expected_status}
          </p>
        </div>
        <div className="page__actions">
          <Link to={`/monitors/${id}/edit`} className="btn">
            Edit
          </Link>
          <button
            className="btn btn--danger"
            disabled={del.isPending}
            onClick={() => {
              if (confirmDelete(monitor.data!.name)) {
                del.mutate(id, { onSuccess: () => navigate("/") });
              }
            }}
          >
            Delete
          </button>
        </div>
      </header>

      <div className="range-tabs">
        {RANGES.map((r) => (
          <button
            key={r}
            className={r === range ? "btn btn--active" : "btn"}
            onClick={() => setRange(r)}
          >
            {r}
          </button>
        ))}
      </div>

      {/* TODO (you): percentile row. GET /api/checks/stats?monitor_id&range
          P50 / P95 / P99 / uptime, four big numbers above the chart. */}
      <section className="panel panel--todo">
        <strong>Percentiles</strong> — build{" "}
        <code>check_stats</code> in <code>api/app/routers/checks.py</code>
      </section>

      {/* TODO (you): the big chart. GET /api/checks/series?monitor_id&range
          Recharts LineChart, avg and p95 as two lines. Import from recharts --
          it is already a dependency. Show gaps where buckets are empty; a gap
          is the picture of an outage and interpolating hides it. */}
      <section className="panel panel--todo" style={{ minHeight: 220 }}>
        <strong>Response time chart</strong> — build{" "}
        <code>check_series</code> in <code>api/app/routers/checks.py</code>
      </section>

      <section className="panel">
        <h2>Recent checks</h2>
        <table className="table">
          <thead>
            <tr>
              <th></th>
              <th>Time</th>
              <th>Code</th>
              <th>Response</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>
            {checks.data?.slice(0, 50).map((c) => (
              <tr key={c.id}>
                <td>
                  <StatusDot status={c.status} size={8} pulse={false} />
                </td>
                <td>{new Date(c.checked_at).toLocaleTimeString()}</td>
                <td>{c.status_code ?? "—"}</td>
                <td>{ms(c.response_time_ms)}</td>
                <td className="table__error">{c.error_message ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h2>Incidents</h2>
        {incidents.data?.length === 0 && <p className="muted">No incidents. Good.</p>}
        <ul className="incidents">
          {incidents.data?.map((i) => (
            <li key={i.id}>
              <Link to={`/incidents/${i.id}`}>
                <StatusDot status={i.resolved_at ? "up" : "down"} size={8} />
                <span>{i.cause ?? "Unknown cause"}</span>
                <span className="muted">
                  {relativeTime(i.started_at)} ·{" "}
                  {i.resolved_at ? duration(i.duration_secs) : "ongoing"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
