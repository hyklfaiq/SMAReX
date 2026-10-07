"""Declarative base, shared column types and enum bindings.

The Python enums mirror the PostgreSQL ``public.*`` enum types created in
supabase/migrations/0001 so the database stays the single source of truth.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    MetaData,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Supabase owns identity in the `auth` schema. SMAReX never queries that table,
# but several columns reference auth.users(id) as a foreign key. SQLAlchemy
# only knows about tables present in its own metadata, so without a stub here
# it cannot resolve those references and raises NoReferencedTableError the
# first time several related rows are flushed in one transaction.
#
# Declaring the table is enough: it makes the foreign-key graph complete, which
# is what the unit of work needs in order to order INSERTs. No column beyond the
# primary key is modelled, and nothing here ever emits a statement against it.
# ---------------------------------------------------------------------------
auth_users = Table(
    "users",
    Base.metadata,
    Column("id", PGUUID(as_uuid=True), primary_key=True),
    schema="auth",
    extend_existing=True,
)


# ---------------------------------------------------------------------------
# Enumerations (values must match the Postgres enum labels exactly)
# ---------------------------------------------------------------------------
class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"


class SecurityStatus(str, enum.Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    SAFE = "safe"
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    ERROR = "error"


class PublicationStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    PUBLISHED = "published"
    REJECTED = "rejected"
    DELETED = "deleted"


class AiSummaryStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    SAFE = "safe"
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    ERROR = "error"


class FlagStatus(str, enum.Enum):
    OPEN = "open"
    REVIEWED = "reviewed"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"


class FlagReason(str, enum.Enum):
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    COPYRIGHT_VIOLATION = "copyright_violation"
    IRRELEVANT = "irrelevant"
    PLAGIARISM = "plagiarism"
    BROKEN_OR_CORRUPT = "broken_or_corrupt"
    OTHER = "other"


def enum_column(enum_cls: type[enum.Enum], name: str, **kwargs) -> Mapped:
    """Build a column bound to a native Postgres enum type.

    ``name`` must be the label of the type created in
    supabase/migrations/0001, e.g. ``user_role`` -- not the Python class name.
    """
    return mapped_column(
        SAEnum(
            enum_cls,
            name=name,
            native_enum=True,
            # Map our UPPER attribute names onto the lowercase Postgres labels.
            values_callable=lambda e: [m.value for m in e],
            create_constraint=False,
            validate_strings=True,
        ),
        **kwargs,
    )


# Python enum -> Postgres type name. Keeps models free of magic strings.
ENUM_TYPE_NAMES: dict[type[enum.Enum], str] = {
    UserRole: "user_role",
    SecurityStatus: "security_status",
    PublicationStatus: "publication_status",
    AiSummaryStatus: "ai_summary_status",
    ScanStatus: "scan_status",
    FlagStatus: "flag_status",
    FlagReason: "flag_reason",
}


# Reusable column definitions -----------------------------------------------
UUIDPk = Mapped[uuid.UUID]
uuid_pk = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
uuid_fk = lambda **kw: mapped_column(PGUUID(as_uuid=True), **kw)  # noqa: E731
created_at = mapped_column(
    DateTime(timezone=True), server_default=None, default=utcnow, nullable=False
)
updated_at = mapped_column(
    DateTime(timezone=True), server_default=None, default=utcnow, onupdate=utcnow,
    nullable=False,
)