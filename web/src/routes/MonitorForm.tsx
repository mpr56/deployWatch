// Add / edit a monitor.
//
// The "Test now" button is the whole point of this screen: run one real check
// and show the result BEFORE saving. It is a small feature and it is the
// difference between confidently adding a monitor and adding a typo you find
// out about an hour later.

import { useEffect, useRef, useState } from "react";
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
import { HTTP_METHODS, type HttpMethod } from "../types";

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
  method: "GET" as HttpMethod,
  // Edited as "Name: value" lines so a header block pasted from curl or
  // devtools just works. Parsed into an object on submit.
  headers: "",
  body: "",
};

// GET and HEAD requests carry no body; the field is hidden for them.
const takesBody = (m: HttpMethod) => m !== "GET" && m !== "HEAD";

function headersToText(h: Record<string, string>): string {
  return Object.entries(h)
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
}

function parseHeaders(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [i, raw] of text.split("\n").entries()) {
    const line = raw.trim();
    if (!line) continue;
    const colon = line.indexOf(":");
    if (colon < 1) throw new Error(`Header line ${i + 1} needs the form "Name: value"`);
    out[line.slice(0, colon).trim()] = line.slice(colon + 1).trim();
  }
  return out;
}

export function MonitorForm() {
  const params = useParams();
  const id = params.id ? Number(params.id) : undefined;
  const navigate = useNavigate();

  const existing = useMonitor(id ?? 0);
  const [form, setForm] = useState(BLANK);
  const [advanced, setAdvanced] = useState(false);
  const [shapeError, setShapeError] = useState<string | null>(null);

  useEffect(() => {
    if (id && existing.data) {
      const { name, url, interval_secs, expected_status, timeout_ms, degraded_ms, method, headers, body } =
        existing.data;
      setForm({
        name, url, interval_secs, expected_status, timeout_ms, degraded_ms, method,
        headers: headersToText(headers),
        body: body ?? "",
      });
      // Open the section when there is something in it to see.
      if (method !== "GET" || Object.keys(headers).length || body) setAdvanced(true);
    }
  }, [id, existing.data]);

  const create = useCreateMonitor();
  const update = useUpdateMonitor(id ?? 0);
  const test = useTestMonitor();

  const { canEdit, openGate, role } = useAuth();

  const set =
    (k: keyof typeof BLANK) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm({
      ...form,
      [k]:
        e.target.type === "number" || k === "interval_secs"
          ? Number(e.target.value)
          : e.target.value,
    });

  // The API wants headers as an object and no body on GET/HEAD. Returns null
  // (and shows why) when the headers text does not parse.
  function payload() {
    try {
      const headers = parseHeaders(form.headers);
      setShapeError(null);
      return { ...form, headers, body: takesBody(form.method) ? form.body : "" };
    } catch (err) {
      setShapeError((err as Error).message);
      setAdvanced(true);
      return null;
    }
  }

  // Creating validates the URL server-side first, which takes a moment. The ref
  // blocks repeat submits fired before React re-renders the disabled button.
  const submitting = useRef(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting.current) return;
    const body = payload();
    if (!body) return;
    submitting.current = true;
    try {
      if (id) await update.mutateAsync(body);
      else await create.mutateAsync(body);
      navigate("/");
    } catch {
      // shown below via saveError
    } finally {
      submitting.current = false;
    }
  }

  const saving = create.isPending || update.isPending;
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

        <button
          type="button"
          className="form__toggle"
          aria-expanded={advanced}
          onClick={() => setAdvanced(!advanced)}
        >
          {advanced ? "▾" : "▸"} Advanced request
          {!advanced && form.method !== "GET" && <span className="form__hint"> · {form.method}</span>}
        </button>

        {advanced && (
          <div className="form__advanced">
            <div className="form__grid">
              <label>
                Method
                <select value={form.method} onChange={set("method")}>
                  {HTTP_METHODS.map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Headers
              <textarea
                value={form.headers}
                onChange={set("headers")}
                rows={3}
                spellCheck={false}
                placeholder={"Authorization: Bearer <token>\nAccept: application/json"}
              />
              <span className="form__hint">
                One per line. Only you can see the values; other viewers see them masked.
              </span>
            </label>
            {takesBody(form.method) && (
              <label>
                Body
                <textarea
                  value={form.body}
                  onChange={set("body")}
                  rows={5}
                  spellCheck={false}
                  placeholder={'{"ping": true}'}
                />
                <span className="form__hint">
                  Sent as-is. Add a Content-Type header to match, e.g. application/json.
                </span>
              </label>
            )}
          </div>
        )}

        <div className="form__actions">
          <button
            type="button"
            className="btn"
            disabled={!form.url || test.isPending}
            onClick={() => {
              const body = payload();
              if (body) test.mutate(body);
            }}
          >
            {test.isPending ? "Testing…" : "Test now"}
          </button>
          <button type="submit" className="btn btn--primary" disabled={saving}>
            {saving ? "Saving…" : id ? "Save" : "Create monitor"}
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
        {shapeError && <div className="error">{shapeError}</div>}
        {saveError && <div className="error">{saveError.message}</div>}
      </form>
    </div>
  );
}
