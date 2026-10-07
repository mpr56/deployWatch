"""Alert delivery: email (SMTP) and webhook (POST).  v2.

Called by detector.py on state transitions only.
"""

from __future__ import annotations

from ..models import Incident, Monitor


async def dispatch(monitor: Monitor, incident: Incident, event: str) -> None:
    """Send every active alert config for this monitor. `event` is "opened" | "resolved".

    TODO (you, v2):
      - Load active alert_configs for the monitor, fan out with asyncio.gather.
      - Email: `aiosmtplib` (add it to requirements), pointed at Mailpit from
        docker-compose -- SMTP_HOST/SMTP_PORT in .env. Read the mail at
        http://localhost:8025. Do not test against a real inbox.
      - Webhook: httpx POST, short timeout, JSON body
        {event, monitor: {id, name, url}, incident: {...}}.

    Non-negotiable: a failing alert channel must never break the checker.
    Wrap each send, log the failure, keep going. The monitoring system going
    down because a webhook endpoint went down is the joke that writes itself.

    Worth doing early: a `sent_alerts` row per (incident, config, event) so a
    retry cannot double-send. Nobody wants two pages for one outage.
    """
    raise NotImplementedError("app/alerts/dispatch.py:dispatch")
