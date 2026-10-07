"""The checker. One async loop, bounded concurrency, no threads.

The whole design constraint: 500 monitors must be the same process shape as 5.
That means no thread per monitor and no task-per-monitor fan-out without a
ceiling -- one event loop, asyncio.gather over a semaphore, one shared
httpx.AsyncClient so connections get reused.

`classify` below is written for you as a worked example of the three-state
rule. The two functions after it are yours.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import CheckStatus


@dataclass(slots=True)
class CheckResult:
    status: CheckStatus
    status_code: int | None = None
    response_time_ms: int | None = None
    error_message: str | None = None


def classify(
    status_code: int | None,
    elapsed_ms: int | None,
    expected_status: int,
    degraded_ms: int,
) -> CheckStatus:
    """Three states, not two.

    down     -- no response at all, or the wrong status code
    degraded -- right status code, but slower than the monitor's threshold
    up       -- right status code, fast enough

    A site returning 200s in 3 seconds is technically fine and practically
    broken. That case is the entire reason `degraded` exists, and it is the
    state people forget to design for.
    """
    if status_code is None or status_code != expected_status:
        return CheckStatus.down
    if elapsed_ms is not None and elapsed_ms >= degraded_ms:
        return CheckStatus.degraded
    return CheckStatus.up


async def run_check(
    url: str,
    timeout_ms: int,
    expected_status: int,
    degraded_ms: int,
    client=None,
) -> CheckResult:
    """Perform exactly one HTTP check. Never raises -- a failure IS the result.

    TODO (you). Roughly:
      1. `time.perf_counter()` before and after. Measure the request only.
      2. `await client.get(url, timeout=timeout_ms / 1000, follow_redirects=True)`
      3. Return `classify(...)` on success.
      4. Catch `httpx.TimeoutException`, `httpx.RequestError`, and a bare
         `Exception` last. Each returns CheckStatus.down with a short,
         human-readable error_message -- that string is what shows up as the
         incident's "cause", so "connection refused" beats
         "ConnectError(...)" with a stack trace in it.

    Two things that will bite you:
      - `client=None` means "make your own" -- that path is for the "Test now"
        button, which runs a single check with no pool. The scheduler passes a
        shared client in. Do not create a client per check in the hot path.
      - A timeout is `down` with `response_time_ms=None`, not
        `response_time_ms=timeout_ms`. Recording the timeout value as a real
        timing quietly poisons every percentile you compute later.
    """
    raise NotImplementedError("app/checker/engine.py:run_check")


async def run_due_checks(monitor_ids: list[int]) -> int:
    """Check a batch of monitors concurrently and persist the results.

    Returns how many checks were written.

    TODO (you). The shape:

        sem = asyncio.Semaphore(settings.checker_concurrency)

        async with httpx.AsyncClient() as client:
            async def one(monitor):
                async with sem:
                    return monitor, await run_check(..., client=client)

            results = await asyncio.gather(*(one(m) for m in monitors))

    Then bulk-insert every result in ONE statement -- not one INSERT per
    monitor. `session.execute(insert(Check), [dict, dict, ...])` does it.

    After the write, hand each (monitor, result) to detector.evaluate() so
    incidents open and close. Do that after the checks are committed: an
    incident that references checks not yet in the database is a race you will
    debug at 2am.

    Watch out for: one slow monitor must not delay the others. gather already
    gives you that, as long as every check has its own timeout and run_check
    genuinely never raises -- one exception escaping gather kills the batch.
    """
    raise NotImplementedError("app/checker/engine.py:run_due_checks")
