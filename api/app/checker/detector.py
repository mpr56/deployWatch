"""Incident state machine.  up -> down -> recovering -> up

The rule that makes this non-trivial: a single failed check is not an incident,
and a single successful check is not a recovery. Both transitions need
consecutive confirmation, and the two thresholds are deliberately different
(settings.incident_open_after / incident_close_after).

    up          N consecutive failures      -> open incident
    down        1 success                   -> recovering (incident stays open)
    recovering  M consecutive successes     -> close incident
    recovering  1 failure                   -> back to down, same incident

The last transition is the one people miss. A service flapping every 30 seconds
should produce ONE long incident, not forty short ones.
"""

from __future__ import annotations

from ..models import CheckStatus


async def evaluate(monitor_id: int, result_status: CheckStatus) -> None:
    """Fold one check result into the incident state for a monitor.

    TODO (you, v2).

    Where does the state live? Two options, pick deliberately:

      (a) Derive it. Query the last N checks for this monitor and count the
          run. No new state to keep in sync, correct after a restart, costs one
          indexed query per check. Start here.

      (b) Keep an in-memory dict of consecutive counts. Faster, and wrong every
          time the process restarts mid-incident.

    (a) is right until it measurably isn't.

    Opening: INSERT an incident with started_at = the FIRST failing check's
    timestamp, not now(). The outage began when it began, not when you noticed
    on the third check -- getting this wrong understates every duration you
    will ever report.

    Closing: set resolved_at, compute duration_secs, and set checks_failed to
    the real count. The partial unique index incidents_one_open_per_monitor
    means a double-open raises instead of silently creating two -- let it raise
    and handle the conflict rather than checking first.

    `cause` is the error_message from the first failing check.

    Then fire alerts on transition only -- open and close -- never on every
    failing check. See alerts/dispatch.py.
    """
    raise NotImplementedError("app/checker/detector.py:evaluate")
