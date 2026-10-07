"""Comments, ratings and bookmarks."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import desc, func, select

from app.api.deps import CurrentUser, DbSession, load_resource
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import Comment, Rating, Resource, SavedResource
from app.schemas import (
    CommentCreate,
    CommentOut,
    MessageResponse,
    RatingSummary,
    RatingUpsert,
)
from app.security.permissions import assert_can_view_resource

router = APIRouter(tags=["interactions"])


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
@router.get(
    "/resources/{resource_id}/comments",
    response_model=list[CommentOut],
)
async def list_comments(
    resource_id: str,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
):
    resource = await load_resource(db, resource_id)
    assert_can_view_resource(user, resource)

    result = await db.execute(
        select(Comment)
        .where(Comment.resource_id == resource.id)
        .order_by(desc(Comment.created_at))
        .limit(limit)
    )
    viewer = uuid.UUID(user.id)
    comments = result.scalars().all()

    return [
        CommentOut(
            **{
                "id": str(c.id),
                "resource_id": str(c.resource_id),
                "comment": c.comment,
                "is_hidden": c.is_hidden,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "author": c.author.public_dict() if c.author else None,
                # Hidden comments stay visible to their author and to admins.
                "can_delete": user.is_admin or c.user_id == viewer,
            }
        )
        for c in comments
        if not c.is_hidden or c.user_id == viewer or user.is_admin
    ]


@router.post(
    "/resources/{resource_id}/comments",
    response_model=CommentOut,
    status_code=201,
)
async def add_comment(
    resource_id: str,
    payload: CommentCreate,
    db: DbSession,
    user: CurrentUser,
):
    resource = await load_resource(db, resource_id)
    assert_can_view_resource(user, resource)

    comment = Comment(
        resource_id=resource.id,
        user_id=uuid.UUID(user.id),
        comment=payload.comment,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return CommentOut(
        **{
            "id": str(comment.id),
            "resource_id": str(comment.resource_id),
            "comment": comment.comment,
            "is_hidden": comment.is_hidden,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
            "author": user.profile.public_dict() if user.profile else None,
            "can_delete": True,
        }
    )


@router.delete("/comments/{comment_id}", response_model=MessageResponse)
async def delete_comment(
    comment_id: str,
    db: DbSession,
    user: CurrentUser,
):
    """Authors and admins only."""
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if comment is None:
        raise NotFoundError("That comment could not be found.")

    if not (user.is_admin or comment.user_id == uuid.UUID(user.id)):
        raise AuthorizationError("You can only remove your own comments.")

    db.delete(comment)
    await db.commit()
    return MessageResponse(message="Comment deleted.")
# ---------------------------------------------------------------------------
# Ratings -- one per user per resource, enforced by a unique constraint
# ---------------------------------------------------------------------------
@router.get("/resources/{resource_id}/rating", response_model=RatingSummary)
async def get_rating(resource_id: str, db: DbSession, user: CurrentUser):
    resource = await load_resource(db, resource_id)
    assert_can_view_resource(user, resource)

    average = await db.scalar(
        select(func.avg(Rating.rating)).where(Rating.resource_id == resource.id)
    )
    count = await db.scalar(
        select(func.count()).select_from(Rating).where(Rating.resource_id == resource.id)
    )
    mine = await db.scalar(
        select(Rating.rating).where(
            Rating.resource_id == resource.id,
            Rating.user_id == uuid.UUID(user.id),
        )
    )

    return RatingSummary(
        resource_id=str(resource.id),
        average=round(float(average or 0), 2),
        count=int(count or 0),
        my_rating=mine,
    )


@router.put("/resources/{resource_id}/rating", response_model=RatingSummary)
async def upsert_rating(
    resource_id: str,
    payload: RatingUpsert,
    db: DbSession,
    user: CurrentUser,
):
    """Rate a resource. Re-rating replaces the previous score."""
    resource = await load_resource(db, resource_id)
    assert_can_view_resource(user, resource)

    viewer = uuid.UUID(user.id)
    existing = await db.scalar(
        select(Rating).where(
            Rating.resource_id == resource.id, Rating.user_id == viewer
        )
    )

    if existing is None:
        db.add(Rating(resource_id=resource.id, user_id=viewer, rating=payload.rating))
    else:
        existing.rating = payload.rating

    await db.commit()

    # The trigger on `ratings` refreshes resources.rating_avg / rating_count.
    await db.refresh(resource)

    return RatingSummary(
        resource_id=str(resource.id),
        average=round(float(resource.rating_avg or 0), 2),
        count=resource.rating_count,
        my_rating=payload.rating,
    )


@router.delete("/resources/{resource_id}/rating", response_model=MessageResponse)
async def delete_rating(resource_id: str, db: DbSession, user: CurrentUser):
    resource = await load_resource(db, resource_id)
    result = await db.execute(
        select(Rating).where(
            Rating.resource_id == resource.id,
            Rating.user_id == uuid.UUID(user.id),
        )
    )
    rating = result.scalar_one_or_none()
    if rating is None:
        raise NotFoundError("You have not rated this resource.")

    db.delete(rating)
    await db.commit()
    return MessageResponse(message="Rating removed.")


# ---------------------------------------------------------------------------
# Saved resources (bookmarks)
# ---------------------------------------------------------------------------
@router.get("/saved", response_model=list[dict])
async def list_saved(
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=200),
):
    """The signed-in user's bookmarks, newest first."""
    result = await db.execute(
        select(SavedResource)
        .where(SavedResource.user_id == uuid.UUID(user.id))
        .order_by(desc(SavedResource.created_at))
        .limit(limit)
    )
    saved = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "resource_id": str(s.resource_id),
            "saved_at": s.created_at.isoformat() if s.created_at else None,
            "resource": s.resource.to_summary_dict() if s.resource else None,
        }
        for s in saved
        if s.resource is not None
    ]


@router.post("/resources/{resource_id}/save", response_model=MessageResponse, status_code=201)
async def save_resource(resource_id: str, db: DbSession, user: CurrentUser):
    resource = await load_resource(db, resource_id)
    assert_can_view_resource(user, resource)

    viewer = uuid.UUID(user.id)
    already = await db.scalar(
        select(SavedResource).where(
            SavedResource.resource_id == resource.id, SavedResource.user_id == viewer
        )
    )
    if already is not None:
        return MessageResponse(message="Already saved.")

    db.add(SavedResource(resource_id=resource.id, user_id=viewer))
    await db.commit()
    return MessageResponse(message="Saved to your library.")


@router.delete("/resources/{resource_id}/save", response_model=MessageResponse)
async def unsave_resource(resource_id: str, db: DbSession, user: CurrentUser):
    result = await db.execute(
        select(SavedResource).where(
            SavedResource.resource_id == resource_id,
            SavedResource.user_id == uuid.UUID(user.id),
        )
    )
    saved = result.scalar_one_or_none()
    if saved is None:
        raise NotFoundError("That resource is not in your saved list.")

    db.delete(saved)
    await db.commit()
    return MessageResponse(message="Removed from your saved list.")