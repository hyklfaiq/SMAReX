"""Platform user profile -- one row per authenticated account."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UserRole, enum_column, utcnow

if TYPE_CHECKING:  # pragma: no cover
    from app.models.resource import Resource


class Profile(Base):
    __tablename__ = "profiles"

    # Supabase Auth owns identity; auth.users is the parent record.
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    full_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    role: Mapped[UserRole] = enum_column(
        UserRole, "user_role", default=UserRole.STUDENT, nullable=False
    )
    kulliyyah: Mapped[str | None] = mapped_column(String(120))
    programme: Mapped[str | None] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    resources: Mapped[list["Resource"]] = relationship(  # noqa: F821
        back_populates="owner",
        cascade="all, delete-orphan",
        # owner_id references auth.users.id, which Profile mirrors as its
        # primary key, so the join has to be stated explicitly.
        primaryjoin="Profile.id == Resource.owner_id",
        foreign_keys="Resource.owner_id",
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def display_name(self) -> str:
        return self.full_name.strip() or self.email.split("@")[0]

    def public_dict(self) -> dict:
        """Shape exposed to other users -- never includes internal flags."""
        return {
            "id": str(self.id),
            "full_name": self.display_name,
            "kulliyyah": self.kulliyyah,
            "programme": self.programme,
            "avatar_url": self.avatar_url,
        }