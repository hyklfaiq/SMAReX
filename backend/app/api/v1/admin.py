"""Admin panel: users, resources and security logs. Admin role required."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import desc, func, select

from app.api.deps import AdminUser, DbSession, Storage, load_resource
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import (
    DownloadHistory,
    Profile,
    Resource,
    ScanStatus,
    SecurityLog,
    SecurityStatus,
    UserRole,
)
from app.schemas import MessageResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
async def admin_stats(db: DbSession, admin: AdminUser):
    """Headline numbers for the admin dashboard."""
    total_users = await db.scalar(select(func.count()).select_from(Profile)) or 0
    total_resources = await db.scalar(select(func.count()).select_from(Resource)) or 0
    published = await db.scalar(
        select(func.count())
        .select_from(Resource)
        .where(Resource.security_status == SecurityStatus.SAFE)
    ) or 0
    rejected = await db.scalar(
        select(func.count())
        .select_from(SecurityLog)
        .where(SecurityLog.scan_status.in_([ScanStatus.MALICIOUS, ScanStatus.SUSPICIOUS]))
    ) or 0
    downloads = await db.scalar(select(func.count()).select_from(DownloadHistory)) or 0

    return {
        "total_users": total_users,
        "total_resources": total_resources,
        "safe_resources": published,
        "rejected_uploads": rejected,
        "total_downloads": downloads,
    }


@router.get("/users")
async def admin_list_users(
    db: DbSession,
    admin: AdminUser,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Search users by name or email."""
    stmt = select(Profile).order_by(desc(Profile.created_at)).limit(limit)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(Profile.email.ilike(pattern) | Profile.full_name.ilike(pattern))

    result = await db.execute(stmt)
    return [
        {
            "id": str(p.id),
            "full_name": p.display_name,
            "email": p.email,
            "role": p.role.value,
            "kulliyyah": p.kulliyyah,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in result.scalars().all()
    ]


@router.put("/users/{user_id}/role", response_model=MessageResponse)
async def admin_set_role(
    user_id: str,
    role: str = Query(..., pattern="^(student|admin)$"),
    active: bool | None = Query(default=None),
    db: DbSession = None,
    admin: AdminUser = None,
):
    """Promote/demote a user, or suspend/reactivate an account."""
    target_id = uuid.UUID(user_id)
    if str(target_id) == admin.id:
        raise AuthorizationError("You cannot change your own role.")

    result = await db.execute(select(Profile).where(Profile.id == target_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise NotFoundError("That user could not be found.")

    profile.role = UserRole(role)
    if active is not None:
        profile.is_active = active

    db.add(profile)
    await db.commit()
    return MessageResponse(message="User updated.")
@router.get("/resources")
async def admin_list_resources(
    db: DbSession,
    admin: AdminUser,
    status: str | None = Query(default=None, description="Filter by security_status"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """All resources including unpublished and rejected ones."""
    stmt = select(Resource).order_by(desc(Resource.created_at)).limit(limit)
    if status:
        try:
            stmt = stmt.where(Resource.security_status == SecurityStatus(status))
        except ValueError:
            raise NotFoundError("Unknown security status filter.") from None

    result = await db.execute(stmt)
    return [
        {
            **_resource_admin_row(r),
            "ai_summary_status": r.ai_summary_status.value,
        }
        for r in result.scalars().all()
    ]


def _resource_admin_row(resource: Resource) -> dict:
    return {
        "id": str(resource.id),
        "title": resource.title,
        "subject": resource.subject,
        "kulliyyah": resource.kulliyyah,
        "category": resource.category,
        "owner_id": str(resource.owner_id),
        "owner_name": resource.owner.display_name if resource.owner else None,
        "file_name": resource.file_name,
        "file_size": resource.file_size,
        "file_hash": resource.file_hash,
        "security_status": resource.security_status.value,
        "publication_status": resource.publication_status.value,
        "download_count": resource.download_count,
        "rating_avg": float(resource.rating_avg or 0),
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
    }


@router.delete("/resources/{resource_id}", response_model=MessageResponse)
async def admin_delete_resource(
    resource_id: str,
    db: DbSession,
    admin: AdminUser,
    storage: Storage,
):
    """Moderation: remove any resource and its stored file."""
    resource = await load_resource(db, resource_id)

    path = resource.file_path
    db.delete(resource)
    await db.commit()
    await storage.delete(path)
    return MessageResponse(message="Resource removed.")


@router.get("/security-logs")
async def admin_security_logs(
    db: DbSession,
    admin: AdminUser,
    status: str | None = Query(default=None, description="Filter by scan_status"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """VirusTotal verdicts, newest first. Students cannot reach this endpoint."""
    stmt = select(SecurityLog).order_by(desc(SecurityLog.scan_date)).limit(limit)
    if status:
        try:
            stmt = stmt.where(SecurityLog.scan_status == ScanStatus(status))
        except ValueError:
            raise NotFoundError("Unknown scan status filter.") from None

    result = await db.execute(stmt)
    return [
        {
            "id": str(entry.id),
            "resource_id": str(entry.resource_id) if entry.resource_id else None,
            "user_id": str(entry.user_id) if entry.user_id else None,
            "file_name": entry.file_name,
            "file_size": entry.file_size,
            "file_hash": entry.file_hash,
            "scan_status": entry.scan_status.value,
            "scan_result": entry.scan_result,
            "scan_date": entry.scan_date.isoformat() if entry.scan_date else None,
            "details": entry.details,
        }
        for entry in result.scalars().all()
    ]