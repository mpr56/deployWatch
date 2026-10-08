// Where a monitor's alerts go. Alerts fire on transitions only -- when an
// incident opens and when it resolves -- never on every failing check.

import { useState } from "react";

import { useAlerts, useCreateAlert, useDeleteAlert, useTestAlert } from "../lib/api";
import type { AlertChannel } from "../types";

export function AlertsPanel({ monitorId }: { monitorId: number }) {
  const alerts = useAlerts(monitorId);
  const create = useCreateAlert(monitorId);
  const remove = useDeleteAlert(monitorId);
  const test = useTestAlert();

  const [channel, setChannel] = useState<AlertChannel>("email");
  const [destination, setDestination] = useState("");
  const [testResult, setTestResult] = useState<Record<number, string>>({});

  const onAdd = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate(
      { channel, destination },
      { onSuccess: () => setDestination("") },
    );
  };

  const onTest = (id: number) => {
    setTestResult((r) => ({ ...r, [id]: "sending…" }));
    test.mutate(id, {
      onSuccess: () => setTestResult((r) => ({ ...r, [id]: "sent ✓" })),
      onError: (err) => setTestResult((r) => ({ ...r, [id]: String(err.message) })),
    });
  };

  return (
    <section className="panel">
      <h2>Alerts</h2>
      <p className="muted alerts__hint">
        Notified when an incident opens and when it resolves.
      </p>

      {alerts.data?.length === 0 && (
        <p className="muted">No alerts yet — add an email or webhook below.</p>
      )}

      <ul className="alerts">
        {alerts.data?.map((a) => (
          <li key={a.id} className="alerts__item">
            <span className="alerts__channel">{a.channel}</span>
            <span className="alerts__dest">{a.destination}</span>
            {testResult[a.id] && (
              <span
                className={
                  testResult[a.id] === "sent ✓" ? "alerts__ok" : "alerts__msg"
                }
              >
                {testResult[a.id]}
              </span>
            )}
            <button className="btn btn--sm" onClick={() => onTest(a.id)}>
              Send test
            </button>
            <button
              className="btn btn--sm btn--danger"
              onClick={() => remove.mutate(a.id)}
              disabled={remove.isPending}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>

      <form className="alerts__form" onSubmit={onAdd}>
        <select
          value={channel}
          onChange={(e) => setChannel(e.target.value as AlertChannel)}
        >
          <option value="email">Email</option>
          <option value="webhook">Webhook</option>
        </select>
        <input
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder={channel === "email" ? "you@example.com" : "https://hooks.example.com/…"}
          type={channel === "email" ? "email" : "url"}
          required
        />
        <button className="btn btn--primary" disabled={create.isPending}>
          Add alert
        </button>
      </form>
      {create.error && <p className="error">{create.error.message}</p>}
    </section>
  );
}
