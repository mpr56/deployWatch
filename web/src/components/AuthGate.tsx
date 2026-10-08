// The dialog in front of every change: log in as admin, or try the sandbox.

import { useEffect, useState } from "react";

import { useAuth } from "../lib/auth";

export function AuthGate() {
  const { gateOpen, closeGate, startSandbox, signInWithPassword, signInWithGitHub, me } =
    useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState<"admin" | "sandbox" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!gateOpen) return;
    setError(null);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeGate();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [gateOpen, closeGate]);

  if (!gateOpen) return null;

  const run = async (kind: "admin" | "sandbox", fn: () => Promise<void>) => {
    setBusy(kind);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const limits = me?.sandbox_limits;

  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && closeGate()}>
      <div className="modal__card" role="dialog" aria-modal="true" aria-labelledby="gate-title">
        <div className="modal__head">
          <h2 id="gate-title">Make changes</h2>
          <button className="modal__close" onClick={closeGate} aria-label="Close">
            ×
          </button>
        </div>
        <p className="modal__sub">
          Browsing is open to everyone. To change anything, sign in as the admin or
          try it out in a throwaway sandbox.
        </p>

        <div className="gate">
          <section className="gate__option gate__option--primary">
            <h3>Try the sandbox</h3>
            <p>
              Add monitors, alerts and a status page of your own. No account needed —
              everything is deleted after <strong>5 minutes</strong>.
            </p>
            {limits && (
              <ul className="gate__limits">
                <li>Up to {limits.monitors} monitors, checked every minute</li>
                <li>{limits.webhooks} webhook alerts, {limits.status_pages} status page</li>
                <li>The admin's monitors stay read-only</li>
              </ul>
            )}
            <button
              className="btn btn--primary"
              disabled={busy !== null}
              onClick={() => run("sandbox", startSandbox)}
            >
              {busy === "sandbox" ? "Starting…" : "Start sandbox"}
            </button>
          </section>

          <section className="gate__option">
            <h3>Admin login</h3>
            <form
              className="gate__form"
              onSubmit={(e) => {
                e.preventDefault();
                run("admin", () => signInWithPassword(email, password));
              }}
            >
              <input
                type="email"
                placeholder="Email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <input
                type="password"
                placeholder="Password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button className="btn" disabled={busy !== null}>
                {busy === "admin" ? "Signing in…" : "Sign in"}
              </button>
            </form>
            <button
              className="btn gate__github"
              disabled={busy !== null}
              onClick={() => run("admin", signInWithGitHub)}
            >
              Continue with GitHub
            </button>
          </section>
        </div>

        {error && <p className="error modal__error">{error}</p>}
      </div>
    </div>
  );
}
