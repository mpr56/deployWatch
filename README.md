# DeployWatch

A monitor watches a URL on a schedule. Each check records a status code and a
response time. When checks start failing an incident opens; when they recover it
closes. Charts, alerts and the public status page are all views over those two
tables.

That is the entire mental model. Every screen is either configuring a monitor or
reading its history.

## Running it

Everything is already set up in this repo. Two terminals:

```bash
make api     # http://localhost:8000   interactive docs at /docs
make web     # http://localhost:5173
```

If you are starting from a clean checkout, or the database is gone:

```bash
make setup
```

Other commands worth knowing:

| | |
|---|---|
| `make seed` | wipe and reload fixture data (4 monitors, 24h of checks) |
| `make db-shell` | psql prompt inside the container |
| `make reset` | nuke the database and rebuild it from scratch |

Postgres runs on **5433**, not 5432, so it will not fight anything already
installed locally.

## Fixture data

`make seed` creates four monitors covering every state you need to design for:

| Monitor | State |
|---|---|
| Marketing site | up, fast, occasional blip |
| **API gateway** | **down right now**, open incident |
| **Checkout service** | **degraded right now** (~1.4s responses) |
| Docs | up, with a resolved 58-minute incident in its history |

Two of those are deliberately broken. Design the down state before the up state
— it is easy to make a beautiful all-green dashboard and discover it falls
apart the moment something breaks.

## Layout

```
api/
  migrations/001_init.sql   schema; source of truth, mirrored by models.py
  app/
    main.py                 app + lifespan
    config.py               settings from .env
    db.py                   async engine and session
    models.py               SQLAlchemy
    schemas.py              Pydantic — the API contract
    routers/
      monitors.py           DONE — CRUD + dashboard summary
      checks.py             list DONE; series + percentiles are yours
      incidents.py          DONE — list and detail
      status.py             v3, all yours
    checker/
      engine.py             the HTTP checker            ← start here
      scheduler.py          APScheduler wiring
      detector.py           incident state machine
    alerts/dispatch.py      email + webhook
  scripts/seed.py           fixture generator

web/src/
  lib/status.ts             status → colour, label, sort order. ONE place.
  lib/api.ts                typed fetch + TanStack Query hooks
  lib/format.ts             ms / uptime / duration / relative time
  components/
    MonitorRow.tsx          the atom everything else composes from
    Sparkline.tsx           30 bars of history
    StatusDot.tsx
  routes/                   Dashboard, MonitorDetail, MonitorForm,
                            IncidentDetail, StatusPage
```

## What is built and what is not

Working right now: monitor CRUD, the dashboard (sorted by severity, 24h uptime,
sparklines), monitor detail with its recent-checks table, incident list and
detail.

Not built — deliberately, because it is the interesting part:

| | |
|---|---|
| `checker/engine.py` | the checker itself |
| `checker/scheduler.py` | when checks run |
| `checker/detector.py` | incident state machine |
| `alerts/dispatch.py` | email + webhook |
| `checks.py:check_series` | bucketed data for the chart |
| `checks.py:check_stats` | P50/P95/P99 |
| `status.py` | the whole public page |

Each of those raises `NotImplementedError` or returns a 501 with its own file
path in the message, and each carries a docstring with the design constraints
and the specific traps. **`BUILD_ORDER.md` has the order to do them in.**

Nothing is blocked on the checker: the seed data means every screen has real
data to render before a single check has ever run.

## Conventions

- **`migrations/001_init.sql` is the source of truth for the schema.** No
  Alembic yet — add it once the schema stops moving. Until then, if you change
  the SQL, change `models.py` to match.
- **`schemas.py` and `web/src/types.ts` are the same contract in two
  languages.** Hand-maintained. If they start drifting, generate the TS from
  `localhost:8000/openapi.json`.
- **Status colour and sort logic lives only in `web/src/lib/status.ts`.** If you
  write `status === "down" ? ... : ...` anywhere else, it belongs there instead.
  Two copies start disagreeing and the bug looks like green on one screen and
  red on another.
- **Every query over `checks` is bounded** by a time window and a `LIMIT`. That
  table is the one that gets huge.
