-- Request shape: monitors can call an API endpoint, not just GET a page.
-- Defaults reproduce the old behaviour exactly (plain GET, no headers, no body),
-- so existing monitors are untouched.

BEGIN;

ALTER TABLE monitors
    ADD COLUMN IF NOT EXISTS method  TEXT  NOT NULL DEFAULT 'GET',
    -- Header values often carry API tokens. The API only returns them to
    -- callers who can edit the monitor (see routers/monitors.py).
    ADD COLUMN IF NOT EXISTS headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS body    TEXT;

ALTER TABLE monitors DROP CONSTRAINT IF EXISTS method_known;
ALTER TABLE monitors ADD CONSTRAINT method_known
    CHECK (method IN ('GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'));

COMMIT;
