// The public status page. A DIFFERENT PRODUCT that happens to share a database.
//
// The app is dense and for you; this page is for someone who wants one answer.
// It deliberately imports nothing from ../components -- reuse the dashboard's
// atoms and you inherit the dashboard's density. No nav, no controls, no
// latency numbers, no error messages.

import { useParams } from "react-router-dom";

import { usePublicStatus } from "../lib/api";
import type { CheckStatus, DayState, PublicStatus } from "../types";

const HEADLINE: Record<CheckStatus, string> = {
  up: "All systems operational",
  degraded: "Degraded performance",
  down: "Partial outage",
};

const SERVICE_LABEL: Record<CheckStatus, string> = {
  up: "Operational",
  degraded: "Degraded performance",
  down: "Not responding",
};

const DAY_TITLE: Record<DayState, string> = {
  up: "No downtime",
  partial: "Minor downtime",
  down: "Outage",
  none: "No data",
};

function headline(data: PublicStatus): { text: string; status: CheckStatus | null } {
  const s = data.overall_status;
  if (!s) return { text: "No data yet", status: null };
  const down = data.services.filter((x) => x.status === "down").length;
  if (s === "down" && down === data.services.length) {
    return { text: "Major outage", status: "down" };
  }
  return { text: HEADLINE[s], status: s };
}

function blurb(data: PublicStatus, status: CheckStatus | null): string {
  if (data.description) return data.description;
  const down = data.services.filter((x) => x.status === "down").length;
  if (status === "down")
    return `${down === 1 ? "One service is" : `${down} services are`} not responding. We are aware and investigating.`;
  if (status === "degraded") return "Some services are responding slowly. Everything is reachable.";
  return "Everything is running normally.";
}

function since(iso: string): string {
  return new Date(iso).toLocaleString([], {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function minutes(secs: number | null): string {
  if (secs == null) return "";
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.round(secs / 60)}m`;
  return `${Math.floor(secs / 3600)}h ${Math.round((secs % 3600) / 60)}m`;
}

export function StatusPage() {
  const slug = useParams().slug ?? "";
  const { data, isLoading, error } = usePublicStatus(slug);

  if (isLoading) return <div className="sp" />;
  if (error || !data) {
    return (
      <div className="sp">
        <div className="sp__inner">
          <h1 className="sp__headline">Status page not found</h1>
        </div>
      </div>
    );
  }

  const head = headline(data);

  return (
    <div className="sp">
      <div className="sp__inner">
        <div className="sp__brand">{data.title}</div>

        <div className="sp__hero">
          <span className={`sp__dot sp--${head.status ?? "none"}`} />
          <h1 className="sp__headline">{head.text}</h1>
        </div>
        <p className="sp__blurb">{blurb(data, head.status)}</p>

        <div className="sp__services">
          {data.services.map((s) => (
            <section key={s.name}>
              <div className="sp__svc-head">
                <span className="sp__svc-name">{s.name}</span>
                <span className={`sp__svc-status sp-text--${s.status ?? "none"}`}>
                  {s.status ? SERVICE_LABEL[s.status] : "No data"}
                </span>
              </div>
              <div className="sp__days" role="img" aria-label={`${s.name}: 90 days of uptime`}>
                {s.days.map((d) => (
                  <span
                    key={d.date}
                    className={`sp__day sp-day--${d.state}`}
                    title={`${d.date} · ${DAY_TITLE[d.state]}`}
                  />
                ))}
              </div>
              <div className="sp__svc-foot">
                <span>90 days ago</span>
                <span>
                  {s.uptime_pct != null ? `${s.uptime_pct.toFixed(2)}% uptime` : "—"}
                </span>
                <span>today</span>
              </div>
            </section>
          ))}
        </div>

        <div className="sp__incidents">
          <div className="sp__label">Recent incidents</div>
          {data.incidents.length === 0 && (
            <p className="sp__none">No incidents in the last 30 days.</p>
          )}
          {data.incidents.map((i, n) => (
            <div key={n} className="sp__incident">
              <div className="sp__incident-title">{i.title}</div>
              <div className="sp__incident-meta">
                {i.resolved_at
                  ? `Resolved · ${since(i.started_at)} · down ${minutes(i.duration_secs)}`
                  : `Investigating · started ${since(i.started_at)} · ongoing`}
              </div>
            </div>
          ))}
        </div>

        <div className="sp__footer">
          Updated {new Date(data.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · powered by DeployWatch
        </div>
      </div>
    </div>
  );
}
