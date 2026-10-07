import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { MonitorRow } from "../components/MonitorRow";
import { useMonitors } from "../lib/api";
import { bySeverity, overallStatus, statusColor } from "../lib/status";

export function Dashboard() {
  const { data, isLoading, error } = useMonitors();
  const [sort, setSort] = useState<"severity" | "name">("severity");

  const monitors = useMemo(() => {
    if (!data) return [];
    const copy = [...data];
    return sort === "severity"
      ? copy.sort(bySeverity)
      : copy.sort((a, b) => a.name.localeCompare(b.name));
  }, [data, sort]);

  const overall = overallStatus(monitors);

  if (isLoading) return <div className="page">Loading…</div>;
  if (error) return <div className="page error">{String(error)}</div>;

  // The empty state deserves as much care as the populated one -- it is the
  // first thing every new user sees.
  if (monitors.length === 0) {
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

  const down = monitors.filter((m) => m.current_status === "down").length;
  const degraded = monitors.filter((m) => m.current_status === "degraded").length;

  return (
    <div className="page">
      <header className="page__head">
        <div>
          {/* You will look at the all-green version 99% of the time. It should
              read as calm and confident, not as an absence of problems. */}
          <h1 style={{ color: statusColor(overall === "unknown" ? null : overall) }}>
            {down > 0
              ? `${down} monitor${down > 1 ? "s" : ""} down`
              : degraded > 0
                ? `${degraded} degraded`
                : "All systems operational"}
          </h1>
          <p className="page__sub">
            {monitors.length} monitor{monitors.length > 1 ? "s" : ""} · refreshing
            every 30s
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
            Add monitor
          </Link>
        </div>
      </header>

      <div className="rows">
        {monitors.map((m) => (
          <MonitorRow key={m.id} monitor={m} />
        ))}
      </div>
    </div>
  );
}
