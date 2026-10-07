"""Request/response shapes for profiles, resources and engagement."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security.file_validation import validate_tag_list

MAX_TAGS = 15


class ProfilePublic(BaseModel):
    """Shape shown next to a resource or comment."""

    id: str
    full_name: str
    kulliyyah: str | None = None
    programme: str | None = None
    avatar_url: str | None = None


class ProfileMe(ProfilePublic):
    email: str
    role: str
    is_active: bool
    created_at: datetime | None = None


class ProfileUpdate(BaseModel):
    """A user may edit their academic details but never their own role."""

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    kulliyyah: str | None = Field(default=None, max_length=120)
    programme: str | None = Field(default=None, max_length=200)


class ResourceCreate(BaseModel):
    """Metadata sent as multipart fields alongside the PDF."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=300)
    description: str = Field(default="", max_length=8000)
    subject: str = Field(min_length=2, max_length=200)
    kulliyyah: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=60)
    semester: str | None = Field(default=None, max_length=40)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str]) -> list[str]:
        return validate_tag_list(value, limit=MAX_TAGS)


class ResourceSummary(BaseModel):
    id: str
    title: str
    description: str
    subject: str
    kulliyyah: str
    category: str
    semester: str | None
    tags: list[str]
    file_size: int
    security_status: str
    publication_status: str
    ai_summary_status: str
    download_count: int
    view_count: int
    rating_avg: float
    rating_count: int
    created_at: str | None
    updated_at: str | None
    owner: ProfilePublic | None = None


class ResourceDetail(ResourceSummary):
    file_name: str
    file_type: str
    page_count: int | None
    ai_summary: str | None
    ai_keywords: list[str]
    ai_model: str | None
    ai_summary_error: str | None
    owner_id: str
    is_owner: bool = False


class DownloadResponse(BaseModel):
    url: str
    file_name: str
    expires_in: int


class CommentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    comment: str = Field(min_length=1, max_length=4000)


class CommentOut(BaseModel):
    id: str
    resource_id: str
    comment: str
    is_hidden: bool
    created_at: str | None
    updated_at: str | None
    author: ProfilePublic | None
    can_delete: bool = False


class RatingUpsert(BaseModel):
    rating: int = Field(ge=1, le=5)


class RatingSummary(BaseModel):
    resource_id: str
    average: float
    count: int
    my_rating: int | None = None