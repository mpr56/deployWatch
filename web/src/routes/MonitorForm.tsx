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
import { ms } from "../lib/format";

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

  const set = (k: keyof typeof BLANK) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({
      ...form,
      [k]: e.target.type === "number" ? Number(e.target.value) : e.target.value,
    });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (id) await update.mutateAsync(form);
    else await create.mutateAsync(form);
    navigate("/");
  }

  const saveError = create.error ?? update.error;

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
            Interval (seconds)
            <input
              type="number"
              value={form.interval_secs}
              onChange={set("interval_secs")}
              min={10}
            />
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
        {test.error && (
          <div className="test-result error">
            {/* Until checker/engine.py:run_check exists this returns a 500 --
                expected, and it is the first thing worth building. */}
            {String(test.error)}
          </div>
        )}
        {saveError && <div className="error">{String(saveError)}</div>}
      </form>
    </div>
  );
}
