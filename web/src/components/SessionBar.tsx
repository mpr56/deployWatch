// Right side of the top bar: who you are, and the sandbox countdown.

import { useEffect } from "react";

import { useAuth, useSandboxCountdown } from "../lib/auth";

function mmss(secs: number): string {
  return `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;
}

export function SessionBar() {
  const { me, role, openGate, signOut, notice, clearNotice } = useAuth();
  const left = useSandboxCountdown();

  useEffect(() => {
    if (left === 0) signOut("Sandbox ended — your changes have been removed.");
  }, [left, signOut]);

  if (!me?.auth_enabled) return null;

  if (role === "sandbox") {
    return (
      <div className="session session--sandbox">
        <span className="session__pulse" />
        <span className="session__label">Sandbox mode</span>
        <span className="session__text">changes are removed in 5 minutes</span>
        {left != null && (
          <span className={left <= 60 ? "session__timer session__timer--low" : "session__timer"}>
            {mmss(left)}
          </span>
        )}
        <button className="btn btn--sm" onClick={() => signOut()}>
          Exit sandbox
        </button>
      </div>
    );
  }

  if (role === "owner") {
    return (
      <div className="session">
        <span className="session__admin">Admin</span>
        <button className="btn btn--sm" onClick={() => signOut()}>
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="session">
      {notice && (
        <span className="session__notice" onClick={clearNotice}>
          {notice}
        </span>
      )}
      <span className="session__text">Viewing read-only</span>
      <button className="btn btn--sm btn--primary" onClick={openGate}>
        Sign in / Try sandbox
      </button>
    </div>
  );
}
