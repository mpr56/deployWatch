-- DeployWatch schema, v1.
--
-- Four tables. `checks` is the one that gets huge, so it is partitioned by
-- month on checked_at. Everything else is small and boring.
--
-- Run with: make db-migrate   (or see README)

BEGIN;

-- ---------------------------------------------------------------------------
-- enums
-- ---------------------------------------------------------------------------

-- Three states, not two. `degraded` is a 2xx response that took too long.
DO $$ BEGIN
    CREATE TYPE check_status AS ENUM ('up', 'degraded', 'down');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE alert_channel AS ENUM ('email', 'webhook');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- monitors
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS monitors (
    id              BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- No auth in v1. Every monitor belongs to the same nil UUID until there
    -- are real users; the column exists now so adding auth is a backfill,
    -- not a migration of every query.
    user_id         UUID        NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
    name            TEXT        NOT NULL,
    url             TEXT        NOT NULL,
    interval_secs   INTEGER     NOT NULL DEFAULT 60,
    expected_status INTEGER     NOT NULL DEFAULT 200,
    timeout_ms      INTEGER     NOT NULL DEFAULT 10000,
    -- Above this, a successful response is recorded as `degraded` rather than
    -- `up`. Per-monitor because "slow" means different things for a static
    -- page and a search endpoint.
    degraded_ms     INTEGER     NOT NULL DEFAULT 1000,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT interval_sane   CHECK (interval_secs BETWEEN 10 AND 86400),
    CONSTRAINT timeout_sane    CHECK (timeout_ms BETWEEN 100 AND 60000),
    CONSTRAINT degraded_sane   CHECK (degraded_ms > 0 AND degraded_ms <= timeout_ms)
);

CREATE INDEX IF NOT EXISTS monitors_user_idx ON monitors (user_id);
-- The scheduler's hot query: "which monitors are due?"
CREATE INDEX IF NOT EXISTS monitors_active_idx ON monitors (is_active, interval_secs);

-- ---------------------------------------------------------------------------
-- checks  (partitioned monthly by checked_at)
-- ---------------------------------------------------------------------------
--
-- A 60s monitor writes 1,440 rows/day. Ten monitors for a year is ~5.2M rows.
-- Partitioning monthly means "last 24 hours" scans one partition, and dropping
-- old data is a DROP TABLE instead of a DELETE that bloats the heap.
--
-- Postgres requires every partition key column in the primary key, hence the
-- composite (id, checked_at).

CREATE TABLE IF NOT EXISTS checks (
    id               BIGINT       GENERATED ALWAYS AS IDENTITY,
    monitor_id       BIGINT       NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    status           check_status NOT NULL,
    response_time_ms INTEGER,      -- NULL when the request never completed
    status_code      INTEGER,      -- NULL on timeout / DNS failure / connection refused
    error_message    TEXT,
    checked_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    PRIMARY KEY (id, checked_at)
) PARTITION BY RANGE (checked_at);

-- The index that makes the whole product fast. Every read is
-- "this monitor, newest first, within a time window".
CREATE INDEX IF NOT EXISTS checks_monitor_time_idx
    ON checks (monitor_id, checked_at DESC);

-- Creates the monthly partition containing `day`, if it does not exist.
-- Idempotent, so it is safe to call on every boot and from a cron.
CREATE OR REPLACE FUNCTION ensure_checks_partition(day DATE)
RETURNS TEXT AS $$
DECLARE
    start_at DATE := date_trunc('month', day)::DATE;
    end_at   DATE := (date_trunc('month', day) + INTERVAL '1 month')::DATE;
    part     TEXT := 'checks_' || to_char(start_at, 'YYYY_MM');
BEGIN
    IF to_regclass(part) IS NULL THEN
        EXECUTE format(
            'CREATE TABLE %I PARTITION OF checks FOR VALUES FROM (%L) TO (%L)',
            part, start_at, end_at
        );
    END IF;
    RETURN part;
END;
$$ LANGUAGE plpgsql;

-- Last month (for seeded history), this month, next month.
SELECT ensure_checks_partition((now() - INTERVAL '1 month')::DATE);
SELECT ensure_checks_partition(now()::DATE);
SELECT ensure_checks_partition((now() + INTERVAL '1 month')::DATE);

-- ---------------------------------------------------------------------------
-- incidents
-- ---------------------------------------------------------------------------
--
-- An open incident has resolved_at IS NULL. There is at most one open incident
-- per monitor, enforced below -- the detector relies on that being impossible
-- to violate rather than on remembering to check.

CREATE TABLE IF NOT EXISTS incidents (
    id            BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    monitor_id    BIGINT      NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    started_at    TIMESTAMPTZ NOT NULL,
    resolved_at   TIMESTAMPTZ,
    duration_secs INTEGER,
    cause         TEXT,
    checks_failed INTEGER     NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS incidents_one_open_per_monitor
    ON incidents (monitor_id) WHERE resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS incidents_monitor_time_idx
    ON incidents (monitor_id, started_at DESC);

-- ---------------------------------------------------------------------------
-- alert_configs
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS alert_configs (
    id          BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    monitor_id  BIGINT        NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    channel     alert_channel NOT NULL,
    destination TEXT          NOT NULL,   -- email address, or webhook URL
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS alert_configs_monitor_idx
    ON alert_configs (monitor_id) WHERE is_active;

COMMIT;
