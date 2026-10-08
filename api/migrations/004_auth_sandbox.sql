-- Auth: owner vs sandbox. Monitors already carry user_id; status pages now do
-- too, and sandbox sessions are tracked so their data can be swept after 5 min.

BEGIN;

ALTER TABLE status_pages
    ADD COLUMN IF NOT EXISTS user_id UUID NOT NULL
    DEFAULT '00000000-0000-0000-0000-000000000000';
CREATE INDEX IF NOT EXISTS status_pages_user_idx ON status_pages (user_id);

-- One row per anonymous (sandbox) Supabase user, from their first "start".
CREATE TABLE IF NOT EXISTS sandbox_sessions (
    user_id    UUID        PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
