-- v2: one row per alert actually sent, so a retry or a double-evaluation can
-- never page twice for the same (incident, channel, event).

BEGIN;

CREATE TABLE IF NOT EXISTS sent_alerts (
    id              BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id     BIGINT      NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    alert_config_id BIGINT      NOT NULL REFERENCES alert_configs(id) ON DELETE CASCADE,
    event           TEXT        NOT NULL CHECK (event IN ('opened', 'resolved')),
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (incident_id, alert_config_id, event)
);

COMMIT;
