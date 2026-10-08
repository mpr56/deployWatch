"""Pydantic request/response shapes.

These are the API contract. web/src/types.ts is the TypeScript mirror -- keep
them in sync by hand for now; generate types from /openapi.json later if the
drift becomes annoying.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .models import AlertChannel, CheckStatus


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    interval_secs: int = Field(default=60, ge=10, le=86_400)
    expected_status: int = Field(default=200, ge=100, le=599)
    timeout_ms: int = Field(default=10_000, ge=100, le=60_000)
    degraded_ms: int = Field(default=1_000, gt=0)
    is_active: bool = True

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
    is_active: bool | None = None


class MonitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    interval_secs: int
    expected_status: int
    timeout_ms: int
    degraded_ms: int
    is_active: bool
    created_at: datetime
    ssl_expires_at: datetime | None = None
    ssl_error: str | None = None


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
