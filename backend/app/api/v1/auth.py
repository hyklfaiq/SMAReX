"""Session endpoint and profile management."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.models import Profile
from app.schemas import MessageResponse, ProfileMe, ProfileUpdate

router = APIRouter(tags=["auth"])


def _to_me(profile: Profile) -> ProfileMe:
    return ProfileMe(
        **profile.public_dict(),
        email=profile.email,
        role=profile.role.value,
        is_active=profile.is_active,
        created_at=profile.created_at,
    )


@router.get("/auth/me", response_model=ProfileMe)
async def read_me(user: CurrentUser):
    """The browser calls this on load to confirm the session and read the role."""
    return _to_me(user.profile)


@router.get("/auth/config")
async def auth_config():
    """Public settings the login screen needs, with no secrets attached."""
    settings = get_settings()
    return {
        "allowed_email_domains": settings.allowed_domain_list,
        "max_upload_mb": settings.max_upload_mb,
        "sso_enabled": bool(settings.iium_sso_provider_id),
        "sso_provider_id": settings.iium_sso_provider_id or None,
    }


@router.put("/profile", response_model=ProfileMe)
async def update_profile(payload: ProfileUpdate, db: DbSession, user: CurrentUser):
    """A user may edit their academic details. Role and email are not editable."""
    profile = user.profile
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return _to_me(profile)


@router.post("/auth/logout", response_model=MessageResponse)
async def logout():
    """Client-side only.

    Supabase sessions are ended by calling ``supabase.auth.signOut()`` in the
    browser; the server simply acknowledges. Nothing is stored server-side, so
    there is no server-side session to destroy.
    """
    return MessageResponse(message="Signed out.")