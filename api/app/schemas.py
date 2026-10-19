"""Pydantic request/response shapes.

These are the API contract. web/src/types.ts is the TypeScript mirror -- keep
them in sync by hand for now; generate types from /openapi.json later if the
drift becomes annoying.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .models import AlertChannel, CheckStatus


INTERVAL_BUCKETS = (30, 60, 300, 900, 3600)

# Must match the method_known constraint in migrations/005_request_shape.sql.
HttpMethod = Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

MAX_HEADERS = 20
MAX_BODY_CHARS = 16_384
_HEADER_NAME = re.compile(r"^[A-Za-z0-9!#$%&'*+.^_`|~-]+$")  # RFC 9110 token
# httpx computes these from the request itself; letting a monitor set them
# only produces malformed requests.
_RESERVED_HEADERS = {"content-length", "transfer-encoding", "connection"}


def _check_interval(v: int | None) -> int | None:
    if v is not None and v not in INTERVAL_BUCKETS:
        raise ValueError(f"interval_secs must be one of {INTERVAL_BUCKETS}")
    return v


def _check_headers(v: dict[str, str] | None) -> dict[str, str] | None:
    if v is None:
        return v
    if len(v) > MAX_HEADERS:
        raise ValueError(f"at most {MAX_HEADERS} headers")
    for name, value in v.items():
        if not _HEADER_NAME.match(name):
            raise ValueError(f"invalid header name: {name!r}")
        if name.lower() in _RESERVED_HEADERS:
            raise ValueError(f"{name} is set automatically")
        if "\r" in value or "\n" in value or len(value) > 4096:
            raise ValueError(f"invalid value for header {name}")
    return v


def _check_body(v: str | None) -> str | None:
    if v is not None and len(v) > MAX_BODY_CHARS:
        raise ValueError(f"body must be at most {MAX_BODY_CHARS} characters")
    return v or None  # an empty textarea means no body


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    interval_secs: int = Field(default=60, ge=10, le=86_400)
    expected_status: int = Field(default=200, ge=100, le=599)
    timeout_ms: int = Field(default=10_000, ge=100, le=60_000)
    degraded_ms: int = Field(default=1_000, gt=0)
    method: HttpMethod = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    is_active: bool = True

    @field_validator("interval_secs")
    @classmethod
    def interval_bucket(cls, v: int) -> int:
        return _check_interval(v)

    headers_valid = field_validator("headers")(_check_headers)
    body_valid = field_validator("body")(_check_body)

    @field_validator("url")
    @classmethod
    def http_only(cls, v: HttpUrl) -> HttpUrl:
        if v.scheme not in ("http", "https"):
            raise ValueError("url must be http or https")
        return v


class MonitorUpdate(BaseModel):
    """All optional -- PATCH semantics."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    url: HttpUrl | None = None
    interval_secs: int | None = Field(default=None, ge=10, le=86_400)
    expected_status: int | None = Field(default=None, ge=100, le=599)
    timeout_ms: int | None = Field(default=None, ge=100, le=60_000)
    degraded_ms: int | None = Field(default=None, gt=0)
    method: HttpMethod | None = None
    headers: dict[str, str] | None = None
    body: str | None = None  # send null (or "") to clear
    is_active: bool | None = None

    @field_validator("interval_secs")
    @classmethod
    def interval_bucket(cls, v: int | None) -> int | None:
        return _check_interval(v)

    headers_valid = field_validator("headers")(_check_headers)
    body_valid = field_validator("body")(_check_body)


class MonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    interval_secs: int
    expected_status: int
    timeout_ms: int
    degraded_ms: int
    method: str = "GET"
    # Values are redacted for callers who cannot edit the monitor -- they
    # usually hold API tokens. See routers/monitors.py:_redact.
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    is_active: bool
    created_at: datetime
    ssl_expires_at: datetime | None = None
    ssl_error: str | None = None
    is_sandbox: bool = False


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monitor_id: int
    status: CheckStatus
    response_time_ms: int | None
    status_code: int | None
    error_message: str | None
    checked_at: datetime


class MonitorSummary(MonitorOut):
    """What the dashboard renders: one row per monitor, everything precomputed.

    The dashboard must never do N+1 queries -- one request returns every row
    fully populated, sparkline included.
    """

    current_status: CheckStatus | None = None
    last_response_time_ms: int | None = None
    last_checked_at: datetime | None = None
    uptime_24h: float | None = None  # 0.0 - 100.0, None when there are no checks
    sparkline: list[CheckStatus] = Field(default_factory=list)  # oldest -> newest


class CheckStats(BaseModel):
    """Percentiles for the monitor detail header (v2)."""

    count: int
    p50_ms: float | None = None
    p95_ms: float | None = None
    p99_ms: float | None = None
    uptime_pct: float | None = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monitor_id: int
    started_at: datetime
    resolved_at: datetime | None
    duration_secs: int | None
    cause: str | None
    checks_failed: int


class AlertConfigCreate(BaseModel):
    channel: AlertChannel
    destination: str = Field(min_length=3)
    is_active: bool = True


class AlertConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monitor_id: int
    channel: AlertChannel
    destination: str
    is_active: bool


class TestCheckResult(BaseModel):
    """Result of the "Test now" button on the add/edit form.

    Runs one check immediately and returns it without writing to the database.
    """

    status: CheckStatus
    status_code: int | None = None
    response_time_ms: int | None = None
    error_message: str | None = None


class StatusPageIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,39}$")
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    monitor_ids: list[int] = Field(default_factory=list)


class StatusPageOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str | None
    monitor_ids: list[int]
    is_sandbox: bool = False
