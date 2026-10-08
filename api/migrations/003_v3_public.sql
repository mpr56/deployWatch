-- v3: public status pages, the 90-day daily rollup, SSL expiry tracking.

BEGIN;

-- A status page is a named, public selection of monitors. A page showing one
-- service is rarely what anyone wants, so pages own the slug, not monitors.
CREATE TABLE IF NOT EXISTS status_pages (
    id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug        TEXT        NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,39}$'),
    title       TEXT        NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS status_page_monitors (
    status_page_id BIGINT  NOT NULL REFERENCES status_pages(id) ON DELETE CASCADE,
    monitor_id     BIGINT  NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    position       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (status_page_id, monitor_id)
);

-- One row per (monitor, UTC day), filled by a nightly job. The public page
-- reads 90 of these per monitor instead of 90 x 1,440 raw checks.
CREATE TABLE IF NOT EXISTS daily_uptime (
    monitor_id BIGINT  NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    day        DATE    NOT NULL,
    total      INTEGER NOT NULL,
    up         INTEGER NOT NULL,
    degraded   INTEGER NOT NULL,
    down       INTEGER NOT NULL,
    avg_ms     INTEGER,
    PRIMARY KEY (monitor_id, day)
);

ALTER TABLE monitors ADD COLUMN IF NOT EXISTS ssl_expires_at TIMESTAMPTZ;
ALTER TABLE monitors ADD COLUMN IF NOT EXISTS ssl_error      TEXT;
ALTER TABLE monitors ADD COLUMN IF NOT EXISTS ssl_checked_at TIMESTAMPTZ;

COMMIT;
