// One monitor, expanded. Percentile stats, response time chart, recent checks,
// incident history.
//
// The recent-checks table is wired up because /api/checks works. The chart and
// the percentile row need endpoints you have not written yet -- see
// api/app/routers/checks.py.

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Link, useNavigate, useParams } from "react-router-dom";

import { AlertsPanel } from "../components/AlertsPanel";
import { EditLink } from "../components/EditLink";
import { useAuth } from "../lib/auth";
import { StatusDot } from "../components/StatusDot";
import { confirmDelete } from "../lib/confirm";
import {
  useCheckSeries,
  useCheckStats,
  useChecks,
  useDeleteMonitor, useIncidents, useMonitor } from "../lib/api";
import { duration, ms, relativeTime, uptime } from "../lib/format";
import { sslDaysLeft, sslWarning } from "../lib/ssl";
import type { TimeRange } from "../types";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
    </div>
  );
}

function formatTick(iso: string, range: TimeRange): string {
  const d = new Date(iso);
  return range === "7d" || range === "30d"
    ? d.toLocaleDateString([], { month: "short", day: "numeric" })
    : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const RANGES: TimeRange[] = ["1h", "24h", "7d", "30d"];

export function MonitorDetail() {
  const id = Number(useParams().id);
  const [range, setRange] = useState<TimeRange>("24h");

  const monitor = useMonitor(id);
  const checks = useChecks(id, range);
  const incidents = useIncidents(id);
  const stats = useCheckStats(id, range);
  const series = useCheckSeries(id, range);
  const del = useDeleteMonitor();
  const navigate = useNavigate();
  const { canEdit, guard, role } = useAuth();

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
            {monitor.data.ssl_expires_at && !sslWarning(monitor.data.ssl_expires_at, null) && (
              <> · SSL valid {sslDaysLeft(monitor.data.ssl_expires_at)}d</>
            )}
            {sslWarning(monitor.data.ssl_expires_at, monitor.data.ssl_error) && (
              <span className="ssl-badge">
                {sslWarning(monitor.data.ssl_expires_at, monitor.data.ssl_error)}
              </span>
            )}
          </p>
        </div>
        {(!canEdit || role === "owner" || monitor.data.is_sandbox) && (
        <div className="page__actions">
          <EditLink to={`/monitors/${id}/edit`} className="btn">
            Edit
          </EditLink>
          <button
            className="btn btn--danger"
            disabled={del.isPending}
            onClick={() =>
              guard(() => {
                if (confirmDelete(monitor.data!.name)) {
                  del.mutate(id, { onSuccess: () => navigate("/") });
                }
              })
            }
          >
            Delete
          </button>
        </div>
        )}
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

      <section className="stats">
        <Stat label="P50" value={ms(stats.data?.p50_ms)} />
        <Stat label="P95" value={ms(stats.data?.p95_ms)} />
        <Stat label="P99" value={ms(stats.data?.p99_ms)} />
        <Stat label="Uptime" value={uptime(stats.data?.uptime_pct)} />
      </section>

      <section className="panel">
        <h2>Response time</h2>
        <div style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series.data ?? []}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="bucket"
                tickFormatter={(v) => formatTick(v, range)}
                stroke="var(--text-dim)"
                fontSize={11}
                minTickGap={40}
              />
              <YAxis
                stroke="var(--text-dim)"
                fontSize={11}
                width={56}
                tickFormatter={(v) => ms(v)}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--panel)",
                  border: "1px solid var(--border)",
                }}
                labelFormatter={(v) => new Date(v).toLocaleString()}
                formatter={(v: number) => ms(v)}
              />
              <Legend />
              {/* connectNulls=false: empty or all-failed buckets leave a gap.
                  The gap is the outage; interpolating would hide it. */}
              <Line
                type="monotone"
                dataKey="avg_ms"
                name="avg"
                stroke="var(--status-up)"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="p95_ms"
                name="p95"
                stroke="var(--status-degraded)"
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
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

      {canEdit && (role === "owner" || monitor.data.is_sandbox) && <AlertsPanel monitorId={id} />}

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
