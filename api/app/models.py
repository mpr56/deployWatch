"""SQLAlchemy models.

These mirror migrations/001_init.sql -- the SQL file is the source of truth.
If you change one, change the other. (No Alembic yet; add it when the schema
stops moving.)
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CheckStatus(str, enum.Enum):
    up = "up"
    degraded = "degraded"
    down = "down"


class AlertChannel(str, enum.Enum):
    email = "email"
    webhook = "webhook"


# create_type=False: the migration owns these types, not the ORM.
check_status_pg = ENUM(CheckStatus, name="check_status", create_type=False)
alert_channel_pg = ENUM(AlertChannel, name="alert_channel", create_type=False)

NIL_USER = uuid.UUID("00000000-0000-0000-0000-000000000000")


class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=NIL_USER)
    name: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    interval_secs: Mapped[int] = mapped_column(Integer, default=60)
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=10_000)
    degraded_ms: Mapped[int] = mapped_column(Integer, default=1_000)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ssl_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ssl_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssl_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_sandbox(self) -> bool:
        """Created by a sandbox user rather than the owner (see app/auth.py)."""
        from .config import get_settings

        owner = get_settings().owner_user_id
        return self.user_id != (uuid.UUID(owner) if owner else NIL_USER)

    checks: Mapped[list[Check]] = relationship(
        back_populates="monitor", cascade="all, delete-orphan"
    )
    incidents: Mapped[list[Incident]] = relationship(
        back_populates="monitor", cascade="all, delete-orphan"
    )


class Check(Base):
    __tablename__ = "checks"

    # Composite PK because the table is partitioned on checked_at. With a
    # composite key SQLAlchemy will not assume IDENTITY, so say so explicitly.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    monitor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("monitors.id", ondelete="CASCADE")
    )
    status: Mapped[CheckStatus] = mapped_column(check_status_pg)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    monitor: Mapped[Monitor] = relationship(back_populates="checks")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("monitors.id", ondelete="CASCADE")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_secs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    checks_failed: Mapped[int] = mapped_column(Integer, default=0)

    monitor: Mapped[Monitor] = relationship(back_populates="incidents")


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    monitor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("monitors.id", ondelete="CASCADE")
    )
    channel: Mapped[AlertChannel] = mapped_column(alert_channel_pg)
    destination: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SentAlert(Base):
    __tablename__ = "sent_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("incidents.id", ondelete="CASCADE")
    )
    alert_config_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("alert_configs.id", ondelete="CASCADE")
    )
    event: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StatusPage(Base):
    __tablename__ = "status_pages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=NIL_USER)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class StatusPageMonitor(Base):
    __tablename__ = "status_page_monitors"

    status_page_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("status_pages.id", ondelete="CASCADE"), primary_key=True
    )
    monitor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("monitors.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)


class DailyUptime(Base):
    __tablename__ = "daily_uptime"

    monitor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("monitors.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    total: Mapped[int] = mapped_column(Integer)
    up: Mapped[int] = mapped_column(Integer)
    degraded: Mapped[int] = mapped_column(Integer)
    down: Mapped[int] = mapped_column(Integer)
    avg_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SandboxSession(Base):
    __tablename__ = "sandbox_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
