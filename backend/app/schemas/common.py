"""Shared response envelopes and pagination helpers."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class Page(BaseModel, Generic[T]):
    """Standard list envelope: ``{"items": [...], "meta": {...}}``."""

    items: list[T]
    meta: PageMeta

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> "Page[T]":
        total_pages = (total + page_size - 1) // page_size if page_size else 0
        return cls(
            items=items,
            meta=PageMeta(
                page=page,
                page_size=page_size,
                total=total,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_previous=page > 1,
            ),
        )


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    """Envelope every failure uses. ``message`` is always safe to show a user."""

    error: dict