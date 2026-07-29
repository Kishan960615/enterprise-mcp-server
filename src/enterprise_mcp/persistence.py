"""Persistence models, engine lifecycle, and audit storage."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from enterprise_mcp.domain import Principal


class Base(DeclarativeBase):
    pass


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    event_type: Mapped[str] = mapped_column(String(100))
    subject_id: Mapped[str] = mapped_column(String(200), index=True)
    request_id: Mapped[str] = mapped_column(String(100), index=True)
    capability_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    outcome: Mapped[str] = mapped_column(String(50))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64))


class ConnectorRecord(Base):
    __tablename__ = "connectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(50))
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(default=True)


class Database:
    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()


class AuditService:
    """Append audit events with simple tamper-evident hash chaining."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def record(
        self,
        *,
        principal: Principal,
        request_id: str,
        event_type: str,
        outcome: str,
        capability_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        duration_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        async with self._sessions() as session, session.begin():
            previous = await session.scalar(
                select(AuditEvent.event_hash)
                .where(AuditEvent.tenant_id == principal.tenant_id)
                .order_by(AuditEvent.occurred_at.desc())
                .limit(1)
            )
            fingerprint = _fingerprint(arguments) if arguments is not None else None
            event_id = str(uuid4())
            event_hash = _fingerprint(
                {
                    "id": event_id,
                    "tenant": principal.tenant_id,
                    "subject": principal.subject_id,
                    "request": request_id,
                    "event": event_type,
                    "capability": capability_name,
                    "outcome": outcome,
                    "input": fingerprint,
                    "previous": previous,
                }
            )
            session.add(
                AuditEvent(
                    id=event_id,
                    tenant_id=principal.tenant_id,
                    subject_id=principal.subject_id,
                    request_id=request_id,
                    event_type=event_type,
                    capability_name=capability_name,
                    outcome=outcome,
                    duration_ms=duration_ms,
                    input_fingerprint=fingerprint,
                    metadata_json=metadata or {},
                    previous_hash=previous,
                    event_hash=event_hash,
                )
            )
        return event_id

    async def recent(self, principal: Principal, limit: int = 20) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            events = (
                await session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.tenant_id == principal.tenant_id)
                    .order_by(AuditEvent.occurred_at.desc())
                    .limit(min(limit, 100))
                )
            ).all()
        return [
            {
                "id": event.id,
                "occurred_at": event.occurred_at.isoformat(),
                "event_type": event.event_type,
                "subject_id": event.subject_id,
                "capability_name": event.capability_name,
                "outcome": event.outcome,
                "request_id": event.request_id,
            }
            for event in events
        ]


def _fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
