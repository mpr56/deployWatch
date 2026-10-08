// Add / edit a monitor.
//
// The "Test now" button is the whole point of this screen: run one real check
// and show the result BEFORE saving. It is a small feature and it is the
// difference between confidently adding a monitor and adding a typo you find
// out about an hour later.

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { StatusDot } from "../components/StatusDot";
import {
  useCreateMonitor,
  useMonitor,
  useTestMonitor,
  useUpdateMonitor,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { ms } from "../lib/format";

// Must match INTERVAL_BUCKETS in api/app/schemas.py -- the scheduler only runs these.
const INTERVALS = [
  { secs: 30, label: "Every 30 seconds" },
  { secs: 60, label: "Every minute" },
  { secs: 300, label: "Every 5 minutes" },
  { secs: 900, label: "Every 15 minutes" },
  { secs: 3600, label: "Every hour" },
];

const BLANK = {
  name: "",
  url: "",
  interval_secs: 60,
  expected_status: 200,
  timeout_ms: 10_000,
  degraded_ms: 1_000,
};

export function MonitorForm() {
  const params = useParams();
  const id = params.id ? Number(params.id) : undefined;
  const navigate = useNavigate();

  const existing = useMonitor(id ?? 0);
  const [form, setForm] = useState(BLANK);

  useEffect(() => {
    if (id && existing.data) {
      const { name, url, interval_secs, expected_status, timeout_ms, degraded_ms } =
        existing.data;
      setForm({ name, url, interval_secs, expected_status, timeout_ms, degraded_ms });
    }
  }, [id, existing.data]);

  const create = useCreateMonitor();
  const update = useUpdateMonitor(id ?? 0);
  const test = useTestMonitor();

  const { canEdit, openGate, role } = useAuth();

  const set = (k: keyof typeof BLANK) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({
      ...form,
      [k]:
        e.target.type === "number" || k === "interval_secs"
          ? Number(e.target.value)
          : e.target.value,
    });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (id) await update.mutateAsync(form);
      else await create.mutateAsync(form);
      navigate("/");
    } catch {
      // shown below via saveError
    }
  }

  const saveError = create.error ?? update.error;

  if (!canEdit) {
    return (
      <div className="page page--narrow">
        <h1>{id ? "Edit monitor" : "Add monitor"}</h1>
        <section className="panel">
          <p>Sign in as admin, or start a 5-minute sandbox, to add or change monitors.</p>
          <button className="btn btn--primary" onClick={openGate}>
            Sign in / Try sandbox
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="page page--narrow">
      <h1>{id ? "Edit monitor" : "Add monitor"}</h1>

      <form onSubmit={onSubmit} className="form">
        <label>
          Name
          <input value={form.name} onChange={set("name")} required />
        </label>

        <label>
          URL
          <input
            type="url"
            value={form.url}
            onChange={set("url")}
            placeholder="https://example.com/health"
            required
          />
        </label>

        <div className="form__grid">
          <label>
            Check interval
            <select value={form.interval_secs} onChange={set("interval_secs")}>
              {INTERVALS.filter((i) => role !== "sandbox" || i.secs >= 60).map((i) => (
                <option key={i.secs} value={i.secs}>
                  {i.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Expected status
            <input
              type="number"
              value={form.expected_status}
              onChange={set("expected_status")}
            />
          </label>
          <label>
            Timeout (ms)
            <input type="number" value={form.timeout_ms} onChange={set("timeout_ms")} />
          </label>
          <label>
            Degraded above (ms)
            <input
              type="number"
              value={form.degraded_ms}
              onChange={set("degraded_ms")}
            />
          </label>
        </div>

        <div className="form__actions">
          <button
            type="button"
            className="btn"
            disabled={!form.url || test.isPending}
            onClick={() => test.mutate(form)}
          >
            {test.isPending ? "Testing…" : "Test now"}
          </button>
          <button type="submit" className="btn btn--primary">
            {id ? "Save" : "Create monitor"}
          </button>
        </div>

        {test.data && (
          <div className="test-result">
            <StatusDot status={test.data.status} />
            <strong>{test.data.status_code ?? "no response"}</strong>
            <span>{ms(test.data.response_time_ms)}</span>
            {test.data.error_message && (
              <span className="error">{test.data.error_message}</span>
            )}
          </div>
        )}
        {test.error && <div className="test-result error">{test.error.message}</div>}
        {saveError && <div className="error">{saveError.message}</div>}
      </form>
    </div>
  );
}
