// Every incident across every monitor, open ones first.

import { Link } from "react-router-dom";

import { StatusDot } from "../components/StatusDot";
import { useIncidents, useMonitors } from "../lib/api";
import { duration, relativeTime } from "../lib/format";

export function Incidents() {
  const incidents = useIncidents();
  const monitors = useMonitors();
  const names = new Map(monitors.data?.map((m) => [m.id, m.name]));

  const list = [...(incidents.data ?? [])].sort((a, b) => {
    const ao = a.resolved_at === null ? 1 : 0;
    const bo = b.resolved_at === null ? 1 : 0;
    return bo - ao || b.started_at.localeCompare(a.started_at);
  });
  const openCount = list.filter((i) => i.resolved_at === null).length;

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <h1>Incidents</h1>
          <p className="page__sub">
            {openCount} open · {list.length} total · an incident opens after
            consecutive failed checks and closes after consecutive passes
          </p>
        </div>
      </header>

      {incidents.isLoading && <p className="muted">Loading…</p>}
      {!incidents.isLoading && list.length === 0 && (
        <section className="panel">
          <p className="muted">No incidents yet. Good.</p>
        </section>
      )}

      {list.length > 0 && (
        <div className="incident-list">
          {list.map((i) => {
            const open = i.resolved_at === null;
            return (
              <Link
                key={i.id}
                to={`/incidents/${i.id}`}
                className={open ? "incident-row incident-row--open" : "incident-row"}
              >
                <StatusDot status={open ? "down" : "up"} size={8} halo />
                <div className="incident-row__main">
                  <div className="row__name">
                    {names.get(i.monitor_id) ?? `Monitor ${i.monitor_id}`}
                  </div>
                  <div className="row__url">{i.cause ?? "Unknown cause"}</div>
                </div>
                <div className="incident-row__meta">
                  {open ? "ongoing" : duration(i.duration_secs)}
                </div>
                <div className="incident-row__meta">{i.checks_failed} failed</div>
                <div className="incident-row__meta">{relativeTime(i.started_at)}</div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
