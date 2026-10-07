import { useParams } from "react-router-dom";

import { StatusDot } from "../components/StatusDot";
import { useIncidents } from "../lib/api";
import { duration } from "../lib/format";

export function IncidentDetail() {
  const id = Number(useParams().id);
  const { data } = useIncidents();
  const incident = data?.find((i) => i.id === id);

  if (!incident) return <div className="page">Loading…</div>;

  const open = incident.resolved_at === null;

  return (
    <div className="page page--narrow">
      <h1>
        <StatusDot status={open ? "down" : "up"} /> {incident.cause ?? "Incident"}
      </h1>

      <dl className="facts">
        <dt>Started</dt>
        <dd>{new Date(incident.started_at).toLocaleString()}</dd>
        <dt>Resolved</dt>
        <dd>
          {incident.resolved_at
            ? new Date(incident.resolved_at).toLocaleString()
            : "Ongoing"}
        </dd>
        <dt>Duration</dt>
        <dd>{duration(incident.duration_secs)}</dd>
        <dt>Checks failed</dt>
        <dd>{incident.checks_failed}</dd>
      </dl>

      {/* TODO (you, v2): the timeline.
          GET /api/incidents/{id}/checks returns the failing checks between
          started_at and resolved_at. Render them as a vertical timeline:
          first failure, each subsequent failure, first recovery, resolved.
          The error messages changing mid-incident (timeout -> 502 -> timeout)
          is often the most diagnostic thing on the screen. */}
      <section className="panel panel--todo">
        <strong>Timeline</strong> — build{" "}
        <code>GET /api/incidents/{"{id}"}/checks</code> in{" "}
        <code>api/app/routers/incidents.py</code>
      </section>
    </div>
  );
}
