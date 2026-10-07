"""Resource -- a safely stored PDF plus metadata and its AI summary."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    AiSummaryStatus,
    Base,
    PublicationStatus,
    SecurityStatus,
    enum_column,
    utcnow,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.models.profile import Profile


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Declared explicitly so the ORM's view of the schema matches the database,
    # where owner_id references auth.users(id) on delete cascade.
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # -- descriptive metadata ------------------------------------------------
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    kulliyyah: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    semester: Mapped[str | None] = mapped_column(String(40))
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(60)), default=list, server_default="{}", nullable=False
    )

    # -- storage metadata ----------------------------------------------------
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_type: Mapped[str] = mapped_column(
        String(100), default="application/pdf", nullable=False
    )
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # -- pipeline state ------------------------------------------------------
    security_status: Mapped[SecurityStatus] = enum_column(
        SecurityStatus, "security_status", default=SecurityStatus.PENDING, nullable=False
    )
    publication_status: Mapped[PublicationStatus] = enum_column(
        PublicationStatus, "publication_status", default=PublicationStatus.DRAFT, nullable=False
    )
    ai_summary_status: Mapped[AiSummaryStatus] = enum_column(
        AiSummaryStatus, "ai_summary_status", default=AiSummaryStatus.PENDING, nullable=False
    )
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(60)), default=list, server_default="{}", nullable=False
    )
    ai_model: Mapped[str | None] = mapped_column(String(120))
    ai_summary_error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)

    # -- counters ------------------------------------------------------------
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating_avg: Mapped[float] = mapped_column(
        Numeric(3, 2), default=0, nullable=False
    )
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Generated in Postgres; declared so the ORM can read it.
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    owner: Mapped["Profile"] = relationship(
        back_populates="resources",
        lazy="joined",
        # owner_id -> auth.users.id, mirrored by profiles.id: state the join.
        primaryjoin="Profile.id == Resource.owner_id",
        foreign_keys="Resource.owner_id",
    )

    __table_args__ = (
        CheckConstraint("file_size > 0", name="file_size_positive"),
        CheckConstraint(
            "publication_status <> 'published' OR security_status = 'safe'",
            name="published_must_be_safe",
        ),
        Index("ix_resources_library", "created_at"),
        Index("ix_resources_kulliyyah", "kulliyyah"),
        Index("ix_resources_category", "category"),
    )

    # -- domain helpers ------------------------------------------------------
    @property
    def is_publicly_visible(self) -> bool:
        return (
            self.publication_status == PublicationStatus.PUBLISHED
            and self.security_status == SecurityStatus.SAFE
        )

    @property
    def has_summary(self) -> bool:
        return bool(self.ai_summary and self.ai_summary.strip())

    def to_summary_dict(self) -> dict:
        """Shape used in list endpoints."""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "subject": self.subject,
            "kulliyyah": self.kulliyyah,
            "category": self.category,
            "semester": self.semester,
            "tags": list(self.tags or []),
            "file_size": self.file_size,
            "security_status": self.security_status.value,
            "publication_status": self.publication_status.value,
            "ai_summary_status": self.ai_summary_status.value,
            "download_count": self.download_count,
            "view_count": self.view_count,
            "rating_avg": float(self.rating_avg or 0),
            "rating_count": self.rating_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "owner": self.owner.public_dict() if self.owner else None,
        }