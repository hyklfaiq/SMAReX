"""FastAPI dependencies: database session, current user, admin gate.

There is deliberately no service layer -- routers talk to the ORM directly and
share the helpers defined here.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import Summarizer
from app.core.exceptions import AuthenticationError
from app.db.session import get_db
from app.models import Profile, Resource
from app.security.auth import extract_bearer_token, resolve_user
from app.security.permissions import require_admin
from app.storage.supabase_storage import SupabaseStorage
from app.virus_total.client import VirusTotalClient

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> object:
    """Resolve and return the signed-in user. 401 when the token is unusable."""
    token = extract_bearer_token(authorization)
    return await resolve_user(token, db)


CurrentUser = Annotated[object, Depends(get_current_user)]


async def get_admin_user(user: CurrentUser) -> object:
    """Dependency for admin-only routes."""
    return require_admin(user)


AdminUser = Annotated[object, Depends(get_admin_user)]


def get_scanner() -> VirusTotalClient:
    return VirusTotalClient()


def get_storage() -> SupabaseStorage:
    return SupabaseStorage()


def get_summarizer_dep() -> Summarizer:
    from app.ai.summarizer import get_summarizer

    return get_summarizer()


Scanner = Annotated[VirusTotalClient, Depends(get_scanner)]
Storage = Annotated[SupabaseStorage, Depends(get_storage)]
SummarizerDep = Annotated[Summarizer, Depends(get_summarizer_dep)]


async def load_resource(db: AsyncSession, resource_id: str) -> Resource:
    """Fetch a resource by id or raise a 404."""
    from app.core.exceptions import NotFoundError

    try:
        result = await db.execute(select(Resource).where(Resource.id == resource_id))
    except Exception:
        # A malformed UUID reaches here as a database type error.
        raise NotFoundError("That resource could not be found.") from None

    resource = result.scalar_one_or_none()
    if resource is None:
        raise NotFoundError("That resource could not be found.")
    return resource