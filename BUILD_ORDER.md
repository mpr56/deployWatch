# Build order

Ship v1 before touching v2. The temptation will be to build the status page
first because it is the prettiest. Resist it.

Each item names the file and what "done" means. The docstring in each file has
the actual design constraints and the traps — read it before you start.

---

## v1 — the core loop

- [x] Schema, partitioning, migrations
- [x] Monitor CRUD
- [x] Dashboard: severity sort, 24h uptime, sparklines
- [x] Monitor detail: recent-checks table
- [x] Fixture data covering up / degraded / down

### 1. `checker/engine.py:run_check` ← start here

One URL in, a `CheckResult` out. Roughly 20 lines.

Done when: `POST /api/monitors/test` returns a real result, and the "Test now"
button on the add-monitor form shows it.

That is the tightest feedback loop in the project — a button in the UI that
proves your checker works, with no scheduler and no database involved.

### 2. `checker/engine.py:run_due_checks`

Many monitors, concurrently, bounded by a semaphore, written in one bulk insert.

Done when: you can call it from a REPL against the seeded monitors and see new
rows land in `checks`.

### 3. `checker/scheduler.py:start`

One job per interval bucket, not one job per monitor.

Done when: `make api` logs "checker scheduler started" instead of the "not wired
up yet" warning, and the dashboard's response times change on their own while
you watch it.

**This is the end of v1.** The core loop is closed: a monitor you add gets
checked forever and the dashboard reflects it. Stop and use it for a day before
moving on — point it at something you actually run.

---

## v2 — incidents and alerts

### 4. `checker/detector.py:evaluate`

The state machine. up → down → recovering → up, with consecutive-count
thresholds in both directions.

Done when: stopping a service you monitor opens exactly one incident after N
failures, and starting it closes that same incident — not a second one.

Test it by monitoring `http://localhost:9999` and starting/stopping a
`python -m http.server 9999`.

### 5. `routers/checks.py:check_stats`

`percentile_cont` for P50/P95/P99 + uptime, one query.

### 6. `routers/checks.py:check_series`

`date_bin` buckets for the chart. Then wire Recharts into
`MonitorDetail.tsx` — it is already a dependency.

### 7. `alerts/dispatch.py`

Email via Mailpit (`docker compose up -d mail`, read it at
http://localhost:8025) and webhook via httpx.

Done when: an incident opening puts mail in Mailpit, and a webhook endpoint that
is down does not break the checker.

### 8. Incident timeline

`GET /api/incidents/{id}/checks` + the timeline UI in `IncidentDetail.tsx`.

---

## v3 — the public layer

### 9. Decide what a status page *is*

`monitors` has no slug. Either a `status_pages` table (slug, title, monitor ids)
or a slug on the user. Probably the former — a status page showing exactly one
service is rarely what anyone wants. This is a schema decision; make it
deliberately before writing the endpoint.

### 10. 90-day daily rollup

A small table, one row per (monitor, day), filled by a nightly job. Do **not**
compute 90 days of uptime from raw checks on every page load — that is 90 ×
1,440 × N rows per request, on the page that gets hammered precisely when things
are broken.

### 11. `routers/status.py:public_status`

Unauthenticated, cacheable, returns names and statuses and nothing else.

### 12. The status page UI

Completely different visual language. No nav, no controls. Do not import
anything from `components/` — the moment you reuse the dashboard's atoms you
inherit the dashboard's density.

### 13. SSL expiry warnings + monthly SLA reports

---

## Design decisions already baked in

Worth knowing they exist so you can change them on purpose rather than
discovering them by accident:

**Three states, not two.** `up` / `degraded` / `down`. Degraded is a correct
status code that took longer than `monitors.degraded_ms` (default 1000ms,
per-monitor). A site returning 200s in 3 seconds is technically fine and
practically broken — that case is the whole reason the state exists.

**Degraded counts as up for uptime.** A slow site is still serving. The one
place this is decided is the `FILTER (WHERE status <> 'down')` in
`routers/monitors.py:list_monitors`.

**Incidents open slowly and close slowly, with different thresholds.**
`INCIDENT_OPEN_AFTER=3`, `INCIDENT_CLOSE_AFTER=2` in `.env`. One blip is not an
incident; one success is not a recovery.

**One open incident per monitor, enforced by a partial unique index.** The
detector cannot create two even if its logic is wrong — the database refuses.

**Broken things sort to the top,** by severity and never alphabetically —
`lib/status.ts:bySeverity`.

**`checks` is partitioned monthly.** `ensure_checks_partition()` runs on every
boot. Add a daily job when you build the scheduler — an INSERT into a month with
no partition fails, and it fails at midnight on the 1st.

**Sparkline bars encode status by height as well as colour.** Failures are full
height, up is 55% — readable without colour vision, and a wall of failures is
visibly taller.
