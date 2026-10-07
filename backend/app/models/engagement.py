"""SavedResource, DownloadHistory and SecurityLog."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ScanStatus, enum_column, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from app.models.resource import Resource


class SavedResource(Base):
    """A bookmark. Strictly private to the owning user."""

    __tablename__ = "saved_resources"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    resource: Mapped["Resource"] = relationship("Resource", lazy="joined")

    __table_args__ = (
        UniqueConstraint("resource_id", "user_id", name="unique"),
        Index("ix_saved_user_created", "user_id", "created_at"),
    )


class DownloadHistory(Base):
    """Audit trail written on every successful secure download."""

    __tablename__ = "download_history"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
    )
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_downloads_resource", "resource_id", "downloaded_at"),
        Index("ix_downloads_user", "user_id", "downloaded_at"),
    )


class SecurityLog(Base):
    """Audit trail of every VirusTotal submission -- stored file or not."""

    __tablename__ = "security_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    scan_status: Mapped[ScanStatus] = enum_column(
        ScanStatus, "scan_status", default=ScanStatus.PENDING, nullable=False
    )
    scan_result: Mapped[dict | None] = mapped_column(JSONB)
    scan_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    details: Mapped[str | None] = mapped_column(Text)
    virustotal_analysis_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("char_length(file_hash) = 64", name="hash_length"),
        Index("ix_security_logs_hash", "file_hash"),
        Index("ix_security_logs_status_date", "scan_status", "scan_date"),
    )
