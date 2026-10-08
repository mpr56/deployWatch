// Monthly SLA report: uptime, downtime and incidents per monitor, plus CSV.

import { useState } from "react";
import { Link } from "react-router-dom";

import { useMonthlyReport } from "../lib/api";
import { duration, ms, uptime } from "../lib/format";
import { statusColor } from "../lib/status";
import type { MonthlyReport } from "../types";

function thisMonth(): string {
  const d = new Date();
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function toCsv(r: MonthlyReport): string {
  const head = ["monitor", "url", "uptime_pct", "sla_target", "sla_met", "incidents",
    "downtime_secs", "checks", "failed_checks", "avg_ms", "ssl_expires_at"];
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const rows = r.monitors.map((m) =>
    [m.name, m.url, m.uptime_pct, r.sla_target, m.sla_met, m.incidents,
      m.downtime_secs, m.checks, m.failed_checks, m.avg_ms, m.ssl_expires_at].map(esc).join(","),
  );
  return [head.join(","), ...rows].join("\n");
}

function download(r: MonthlyReport) {
  const url = URL.createObjectURL(new Blob([toCsv(r)], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `deploywatch-sla-${r.month}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function Reports() {
  const [month, setMonth] = useState(thisMonth());
  const [sla, setSla] = useState(99.9);
  const report = useMonthlyReport(month, sla);
  const met = report.data?.monitors.filter((m) => m.sla_met).length ?? 0;
  const measured = report.data?.monitors.filter((m) => m.sla_met !== null).length ?? 0;

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <h1>Monthly SLA report</h1>
          <p className="page__sub">
            {measured > 0 ? `${met} of ${measured} monitors met ${sla}%` : "No data for this month"}
            {" · "}degraded counts as up, downtime from incidents
          </p>
        </div>
        <div className="page__actions">
          <input
            className="input-inline"
            type="month"
            value={month}
            max={thisMonth()}
            onChange={(e) => e.target.value && setMonth(e.target.value)}
          />
          <select
            className="input-inline"
            value={sla}
            onChange={(e) => setSla(Number(e.target.value))}
          >
            {[99, 99.5, 99.9, 99.95, 99.99].map((v) => (
              <option key={v} value={v}>SLA {v}%</option>
            ))}
          </select>
          <button
            className="btn"
            disabled={!report.data}
            onClick={() => report.data && download(report.data)}
          >
            Export CSV
          </button>
        </div>
      </header>

      <section className="panel">
        <table className="table">
          <thead>
            <tr>
              <th>Monitor</th>
              <th>Uptime</th>
              <th>SLA</th>
              <th>Incidents</th>
              <th>Downtime</th>
              <th>Avg response</th>
              <th>Checks</th>
              <th>SSL expires</th>
            </tr>
          </thead>
          <tbody>
            {report.data?.monitors.map((m) => (
              <tr key={m.id}>
                <td>
                  <Link to={`/monitors/${m.id}`}>{m.name}</Link>
                </td>
                <td>{uptime(m.uptime_pct)}</td>
                <td
                  style={{
                    color:
                      m.sla_met == null ? undefined : statusColor(m.sla_met ? "up" : "down"),
                  }}
                >
                  {m.sla_met == null ? "—" : m.sla_met ? "met" : "missed"}
                </td>
                <td>{m.incidents}</td>
                <td>{m.downtime_secs ? duration(m.downtime_secs) : "—"}</td>
                <td>{ms(m.avg_ms)}</td>
                <td>{m.checks.toLocaleString()}</td>
                <td>
                  {m.ssl_expires_at ? new Date(m.ssl_expires_at).toLocaleDateString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {report.isLoading && <p className="muted">Loading…</p>}
      </section>
    </div>
  );
}
