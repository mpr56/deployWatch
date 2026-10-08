import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { MonitorRow } from "../components/MonitorRow";
import { useIncidents, useMonitors } from "../lib/api";
import { duration, ms, relativeTime, uptime } from "../lib/format";
import { bySeverity, statusColor } from "../lib/status";
import type { MonitorSummary } from "../types";

type Filter = "all" | "down" | "degraded";

export function Dashboard() {
  const { data, isLoading, error } = useMonitors();
  const [sort, setSort] = useState<"severity" | "name">("severity");
  const [filter, setFilter] = useState<Filter>("all");

  const all = data ?? [];
  const down = all.filter((m) => m.current_status === "down");
  const degraded = all.filter((m) => m.current_status === "degraded");
  const up = all.filter((m) => m.current_status === "up");

  const monitors = useMemo(() => {
    const list = all.filter((m) => filter === "all" || m.current_status === filter);
    return sort === "severity"
      ? list.sort(bySeverity)
      : list.sort((a, b) => a.name.localeCompare(b.name));
  }, [all, filter, sort]);

  if (isLoading) return <div className="page">Loading…</div>;
  if (error) return <div className="page error">{String(error)}</div>;

  // The empty state deserves as much care as the populated one -- it is the
  // first thing every new user sees.
  if (all.length === 0) {
    return (
      <div className="page empty">
        <h1>No monitors yet</h1>
        <p>Add a URL and DeployWatch will start checking it on a schedule.</p>
        <Link to="/monitors/new" className="btn btn--primary">
          Add your first monitor
        </Link>
      </div>
    );
  }

  const tabs: { key: Filter; label: string }[] = [
    { key: "all", label: `All ${all.length}` },
    { key: "down", label: `Failing ${down.length}` },
    { key: "degraded", label: `Degraded ${degraded.length}` },
  ];

  return (
    <div className="page page--flush">
      <header className="dash-head">
        <div className="dash-head__row">
          <div>
            <h1>Monitors</h1>
            <p className="page__sub">
              {all.length} active · refreshing every 30s
              {down.length > 0 && ` · ${down.length} down`}
            </p>
          </div>
          <div className="page__actions">
            <button
              className="btn"
              onClick={() => setSort(sort === "severity" ? "name" : "severity")}
            >
              Sort: {sort === "severity" ? "Status" : "Name"}
            </button>
            <Link to="/monitors/new" className="btn btn--primary">
              + Add monitor
            </Link>
          </div>
        </div>
        <div className="tabs">
          {tabs.map((t) => (
            <button
              key={t.key}
              className={filter === t.key ? "tab tab--active" : "tab"}
              onClick={() => setFilter(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>

      <StatStrip all={all} up={up} degraded={degraded} down={down} />

      {down.length > 0 && <DownBanner down={down} />}

      <div className="rows-head">
        <span>Monitor ↓ {sort === "severity" ? "status" : "name"}</span>
        <span className="num">Response</span>
        <span className="num">24h</span>
        <span className="num">Last 30 checks</span>
        <span />
      </div>

      {monitors.map((m) => (
        <MonitorRow key={m.id} monitor={m} />
      ))}
      {monitors.length === 0 && (
        <div className="rows-foot">Nothing matches this filter.</div>
      )}

      <div className="rows-foot">
        {monitors.length} monitor{monitors.length === 1 ? "" : "s"} shown
      </div>
    </div>
  );
}

function StatStrip({
  all,
  up,
  degraded,
  down,
}: Record<"all" | "up" | "degraded" | "down", MonitorSummary[]>) {
  const times = all
    .filter((m) => m.current_status !== "down" && m.last_response_time_ms != null)
    .map((m) => m.last_response_time_ms!);
  const avg = times.length ? times.reduce((a, b) => a + b, 0) / times.length : null;

  const uptimes = all.filter((m) => m.uptime_24h != null).map((m) => m.uptime_24h!);
  const avgUptime = uptimes.length
    ? uptimes.reduce((a, b) => a + b, 0) / uptimes.length
    : null;

  const cells = [
    { label: "Up", value: String(up.length), sub: `of ${all.length} monitors`, color: statusColor("up") },
    { label: "Degraded", value: String(degraded.length), sub: "slower than threshold", color: statusColor("degraded") },
    { label: "Down", value: String(down.length), sub: down.length ? "needs attention" : "all responding", color: statusColor("down") },
    { label: "Avg response", value: ms(avg), sub: "latest check, healthy monitors" },
    { label: "24h uptime", value: uptime(avgUptime), sub: "mean across monitors" },
  ];

  return (
    <div className="strip">
      {cells.map((c) => (
        <div key={c.label} className="strip__cell">
          <div className="strip__label">{c.label}</div>
          <div className="strip__value" style={{ color: c.color }}>
            {c.value}
          </div>
          <div className="strip__sub">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}

function DownBanner({ down }: { down: MonitorSummary[] }) {
  const incidents = useIncidents();
  const first = down[0];
  if (!first) return null;
  const incident = incidents.data?.find(
    (i) => i.monitor_id === first.id && i.resolved_at === null,
  );
  const since = incident
    ? Math.round((Date.now() - new Date(incident.started_at).getTime()) / 1000)
    : null;
  return (
    <div className="banner">
      <span className="dot" style={{ width: 7, height: 7, background: statusColor("down") }} />
      <span className="banner__title">
        {down.length === 1
          ? `${first.name} has been down${since != null ? ` for ${duration(since)}` : ""}`
          : `${down.length} monitors are down`}
      </span>
      <span className="banner__meta">
        {incident
          ? `${incident.cause ?? "unknown cause"} · ${incident.checks_failed} failed checks`
          : `last checked ${relativeTime(first.last_checked_at)}`}
      </span>
      <Link
        to={incident ? `/incidents/${incident.id}` : `/monitors/${first.id}`}
        className="banner__link"
      >
        {incident ? "View incident" : "View monitor"}
      </Link>
    </div>
  );
}
