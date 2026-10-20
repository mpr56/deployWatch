"""Monitor request shape: method, headers and body. No database needed."""

import asyncio
import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from app.auth import Principal
from app.checker.engine import run_check
from app.models import CheckStatus
from app.routers.monitors import REDACTED, _redact
from app.schemas import MonitorCreate, MonitorOut, MonitorUpdate


def _echo_client(seen: list[httpx.Request]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _check(**shape):
    seen: list[httpx.Request] = []

    async def go():
        async with _echo_client(seen) as client:
            return await run_check(
                "https://api.example.com/ping", 5_000, 201, 1_000, client=client, **shape
            )

    return asyncio.run(go()), seen[0]


def test_default_shape_is_a_plain_get():
    result, req = _check()
    assert req.method == "GET"
    assert req.content == b""
    assert "authorization" not in req.headers
    assert result.status == CheckStatus.up


def test_method_headers_and_body_are_sent():
    payload = json.dumps({"ping": True})
    result, req = _check(
        method="POST",
        headers={"Authorization": "Bearer abc", "Content-Type": "application/json"},
        body=payload,
    )
    assert req.method == "POST"
    assert req.headers["authorization"] == "Bearer abc"
    assert req.headers["content-type"] == "application/json"
    assert req.content == payload.encode()
    assert result.status_code == 201


def test_validation():
    m = MonitorCreate(name="a", url="https://x.com", method="PATCH",
                      headers={"X-Key": "1"}, body="")
    assert m.body is None  # empty textarea means no body

    for bad in (
        {"method": "TRACE"},
        {"headers": {"bad name": "x"}},
        {"headers": {"Content-Length": "3"}},
        {"headers": {"X-Evil": "a\r\nInjected: 1"}},
        {"headers": {f"X-{i}": "v" for i in range(21)}},
        {"body": "x" * 20_000},
    ):
        with pytest.raises(ValidationError):
            MonitorUpdate(**bad)


def _out() -> MonitorOut:
    return MonitorOut(
        id=1, name="m", url="https://x.com", interval_secs=60, expected_status=200,
        timeout_ms=10_000, degraded_ms=1_000, method="POST",
        headers={"Authorization": "Bearer secret"}, body='{"k": "secret"}',
        is_active=True, created_at=datetime.now(timezone.utc),
    )


def test_redaction(monkeypatch):
    owner = uuid.uuid4()
    monkeypatch.setattr("app.auth.owner_id", lambda: owner)

    out = _redact(_out(), Principal("visitor"), owner)
    assert out.headers == {"Authorization": REDACTED}
    assert out.body == REDACTED

    sandbox = Principal("sandbox", uuid.uuid4())
    assert _redact(_out(), sandbox, owner).headers == {"Authorization": REDACTED}
    # A sandbox user sees their own monitor's values...
    assert _redact(_out(), sandbox, sandbox.user_id).headers == {"Authorization": "Bearer secret"}
    # ...and the owner sees theirs.
    assert _redact(_out(), Principal("owner", owner), owner).body == '{"k": "secret"}'
