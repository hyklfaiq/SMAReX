"""Authorisation rules.

The backend connects with the service-role key, which bypasses RLS, so every
check that RLS would normally enforce is performed explicitly here:

* a student may only modify or delete their own resources and comments;
* only admins may reach moderation, user management and security logs;
* only published + safe resources are downloadable.
"""

from __future__ import annotations

from app.core.exceptions import AuthorizationError, NotFoundError
from app.models import PublicationStatus, Resource, SecurityStatus
from app.security.auth import AuthenticatedUser


def require_authenticated(user: AuthenticatedUser) -> AuthenticatedUser:
    if user is None:
        raise AuthorizationError("Sign in to continue.")
    return user


def require_admin(user: AuthenticatedUser) -> AuthenticatedUser:
    require_authenticated(user)
    if not user.is_admin:
        raise AuthorizationError(
            "This area is restricted to administrators.",
            code="admin_required",
        )
    return user


def can_modify_resource(user: AuthenticatedUser, resource: Resource) -> bool:
    return user.is_admin or str(resource.owner_id) == user.id


def assert_can_modify_resource(user: AuthenticatedUser, resource: Resource) -> None:
    if not can_modify_resource(user, resource):
        # 404 rather than 403 so ownership of a private item is not disclosed.
        raise NotFoundError("That resource could not be found.")


def can_view_resource(user: AuthenticatedUser | None, resource: Resource) -> bool:
    if user is not None and can_modify_resource(user, resource):
        return True
    return resource.is_publicly_visible


def assert_can_view_resource(
    user: AuthenticatedUser | None, resource: Resource
) -> None:
    if not can_view_resource(user, resource):
        raise NotFoundError("That resource could not be found.")


def can_download_resource(user: AuthenticatedUser, resource: Resource) -> bool:
    """Only published, virus-checked files may be downloaded."""
    return (
        resource.publication_status == PublicationStatus.PUBLISHED
        and resource.security_status == SecurityStatus.SAFE
    )


def assert_can_download_resource(user: AuthenticatedUser, resource: Resource) -> None:
    if not can_download_resource(user, resource):
        raise NotFoundError("That resource is not available for download.")


def can_delete_comment(user: AuthenticatedUser, comment_user_id: str) -> bool:
    return user.is_admin or str(comment_user_id) == user.id


def assert_can_delete_comment(user: AuthenticatedUser, comment_user_id: str) -> None:
    if not can_delete_comment(user, comment_user_id):
        raise AuthorizationError("You can only remove your own comments.")