"""Authentication: verify the Supabase access token and enforce the IIUM Live
domain restriction.

The browser authenticates against Supabase Auth directly and then sends the
resulting JWT as ``Authorization: Bearer <token>``. The backend:

* verifies the JWT signature and expiry,
* rejects tokens whose email is not on the IIUM allow-list,
* rejects tokens for deactivated accounts,
* loads the matching ``profiles`` row, which carries the role.

Verification strategies, in the order they are attempted:

1. **Asymmetric (ES256 / RS256)** -- the modern Supabase default. The signing
   keys are fetched once from the project's JWKS endpoint and cached in memory,
   so verification is local and costs no network call per request. No shared
   secret is stored on the server at all.
2. **Shared secret (HS256)** -- older projects. Verified locally with
   ``SUPABASE_JWT_SECRET``.
3. **Supabase API** -- last resort when neither key material is available.
   Asks ``GET /auth/v1/user`` who the token belongs to.

The strategy is chosen from the token's own ``alg`` header, so a project needs
no configuration beyond filling in its URL.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import PyJWKSet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AccountDisabledError,
    AuthenticationError,
    DomainNotAllowedError,
)
from app.core.logging import get_logger
from app.models import Profile, UserRole

logger = get_logger(__name__)

HS256 = "HS256"
# Asymmetric algorithms Supabase may use for signing keys.
ASYMMETRIC_ALGORITHMS = frozenset({"ES256", "ES384", "ES512", "RS256", "RS384", "RS512"})

_CLOCK_SKEW_SECONDS = 30

# Process-wide cache for the project's signing keys. Verified tokens are common
# and refetching per request would make every call depend on Supabase's uptime.
_jwks_cache: dict[str, Any] = {"jwks": None, "fetched_at": 0.0}


@dataclass(frozen=True)
class AuthenticatedUser:
    """The caller, resolved from a verified access token."""

    id: str
    email: str
    role: UserRole
    is_admin: bool
    profile: Profile | None = None

    @property
    def uuid(self) -> uuid.UUID:
        return uuid.UUID(self.id)


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthenticationError("Sign in to continue.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError("Sign in to continue.")
    return token.strip()


def is_domain_allowed(email: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    domain = email.rsplit("@", 1)[-1].strip().lower()
    return bool(domain) and domain in settings.allowed_domain_list


def peek_header(token: str) -> dict[str, Any]:
    """Read the JWT header without verifying, to choose a strategy."""
    try:
        return jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(
            "Your session is not valid.", code="token_malformed"
        ) from exc


def _decode_with_key(token: str, key: Any, algorithm: str) -> dict[str, Any]:
    """Decode and validate a token against a known signing key.

    ``verify_aud`` is off because Supabase sets ``aud: "authenticated"`` and
    PyJWT rejects any audience that was not explicitly requested, which would
    fail every real token. Audience is Supabase's concern, not ours: proving the
    token was signed by this project's key and has not expired is the whole job.
    """
    try:
        return jwt.decode(
            token,
            key=key,
            algorithms=[algorithm],
            leeway=_CLOCK_SKEW_SECONDS,
            options={"require": ["exp", "sub"], "verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError(
            "Your session has expired. Please sign in again.", code="token_expired"
        ) from exc
    except jwt.InvalidSignatureError as exc:
        logger.info("Rejected access token: signature mismatch")
        raise AuthenticationError(
            "Your session is not valid.", code="token_bad_signature"
        ) from exc
    except jwt.InvalidTokenError as exc:
        logger.info("Rejected access token: %s", type(exc).__name__)
        raise AuthenticationError(
            "Your session is not valid.", code="token_invalid"
        ) from exc


def decode_hs256(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Legacy shared-secret verification."""
    settings = settings or get_settings()
    if not settings.supabase_jwt_secret:
        raise AuthenticationError(
            "Token verification is not configured on the server.",
            code="auth_misconfigured",
        )
    return _decode_with_key(token, settings.supabase_jwt_secret, HS256)


def _anon_headers(settings: Settings) -> dict[str, str]:
    """Supabase's gateway needs an apikey header to identify the project.

    Omitting it produces a 401 even when the bearer token is perfectly valid,
    which is indistinguishable from a bad token unless the code is distinct.
    """
    key = settings.supabase_anon_key or settings.supabase_service_role_key
    headers = {"Accept": "application/json"}
    if key:
        headers["apikey"] = key
    return headers


def jwks_url(settings: Settings) -> str:
    return f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


async def fetch_jwks(settings: Settings, *, force: bool = False) -> PyJWKSet:
    """Fetch (and cache) the project's signing keys."""
    if not force and _jwks_cache["jwks"] is not None:
        age = time.monotonic() - _jwks_cache["fetched_at"]
        if age < settings.jwks_cache_seconds:
            return _jwks_cache["jwks"]

    url = jwks_url(settings)
    try:
        async with httpx.AsyncClient(timeout=settings.auth_verify_timeout_seconds) as client:
            response = await client.get(url, headers=_anon_headers(settings))
    except httpx.HTTPError as exc:
        logger.error("Could not fetch Supabase signing keys: %s", type(exc).__name__)
        raise AuthenticationError(
            "We could not verify your session. Please try again.",
            code="jwks_unavailable",
        ) from exc

    if response.status_code != 200:
        logger.error("JWKS endpoint returned HTTP %s", response.status_code)
        raise AuthenticationError(
            "We could not verify your session. Please try again.",
            code="jwks_unavailable",
        )

    try:
        jwks = PyJWKSet.from_dict(response.json())
    except Exception as exc:  # malformed key set
        logger.error("JWKS response could not be parsed")
        raise AuthenticationError(
            "We could not verify your session. Please try again.",
            code="jwks_unavailable",
        ) from exc

    _jwks_cache["jwks"] = jwks
    _jwks_cache["fetched_at"] = time.monotonic()
    logger.info("Loaded %d Supabase signing key(s)", len(jwks.keys))
    return jwks


def _select_key(jwks: PyJWKSet, kid: str | None) -> Any | None:
    for candidate in jwks.keys:
        if kid and candidate.key_id == kid:
            return candidate
    # A token without a kid, or with one we do not know, is matched by the
    # first key only when the set holds exactly one.
    if not kid and len(jwks.keys) == 1:
        return jwks.keys[0]
    return None


async def verify_with_jwks(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Asymmetric verification against the project's published keys."""
    settings = settings or get_settings()
    header = peek_header(token)
    algorithm = str(header.get("alg") or "")
    kid = header.get("kid")

    if algorithm not in ASYMMETRIC_ALGORITHMS:
        raise AuthenticationError(
            "Unsupported token algorithm.", code="token_bad_algorithm"
        )

    jwks = await fetch_jwks(settings)
    selected = _select_key(jwks, kid)

    if selected is None:
        # The key may have rotated since we cached the set; refetch once.
        logger.info("Unknown key id %s; refetching signing keys", kid)
        jwks = await fetch_jwks(settings, force=True)
        selected = _select_key(jwks, kid)

    if selected is None:
        raise AuthenticationError(
            "Your session is not valid.", code="token_unknown_key"
        )

    return _decode_with_key(token, selected.key, algorithm)


async def fetch_user_via_supabase(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Last-resort verification: ask Supabase who this token belongs to."""
    settings = settings or get_settings()
    if not (settings.supabase_anon_key or settings.supabase_service_role_key):
        raise AuthenticationError(
            "Authentication is not configured on the server.",
            code="auth_misconfigured",
        )

    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    headers = {**_anon_headers(settings), "Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=settings.auth_verify_timeout_seconds) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        logger.error("Supabase user lookup failed: %s", type(exc).__name__)
        raise AuthenticationError(
            "We could not verify your session. Please try again.",
            code="auth_lookup_failed",
        ) from exc

    if response.status_code in (401, 403):
        # Distinct from a local signature failure so the logs stay diagnosable.
        logger.info("Supabase rejected the access token (HTTP %s)", response.status_code)
        raise AuthenticationError("Your session is not valid.", code="token_rejected")

    if response.status_code >= 500:
        raise AuthenticationError(
            "We could not verify your session. Please try again.",
            code="auth_lookup_failed",
        )

    try:
        return response.json()
    except ValueError as exc:
        raise AuthenticationError(
            "We could not verify your session. Please try again.",
            code="auth_lookup_failed",
        ) from exc


async def verify_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Verify a token and return its claims, choosing the strategy itself."""
    settings = settings or get_settings()
    algorithm = str(peek_header(token).get("alg") or "")

    # An unsigned or unexpected algorithm must never reach a decoder, and must
    # never be forwarded to Supabase either: reject it outright.
    if algorithm not in ASYMMETRIC_ALGORITHMS and algorithm != HS256:
        logger.info("Rejected access token with unsupported alg %r", algorithm)
        raise AuthenticationError(
            "Unsupported token algorithm.", code="token_bad_algorithm"
        )

    if algorithm in ASYMMETRIC_ALGORITHMS:
        return await verify_with_jwks(token, settings)

    if settings.supabase_jwt_secret:
        return decode_hs256(token, settings)

    # HS256 with no usable key material: let Supabase decide.
    payload = await fetch_user_via_supabase(token, settings)
    return {
        "sub": str(payload.get("id") or ""),
        "email": payload.get("email") or "",
    }

async def resolve_user(
    token: str,
    db: AsyncSession,
    settings: Settings | None = None,
) -> AuthenticatedUser:
    """Full authentication handshake: token -> verified claims -> profile -> user."""
    settings = settings or get_settings()

    claims = await verify_token(token, settings)
    user_id = str(claims.get("sub") or "")
    email = str(claims.get("email") or "").strip().lower()

    if not user_id:
        raise AuthenticationError("Your session is not valid.", code="token_no_subject")

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise AuthenticationError(
            "Your session is not valid.", code="token_bad_subject"
        ) from exc

    # -- IIUM Live restriction ---------------------------------------------
    if not is_domain_allowed(email, settings):
        logger.warning("Rejected sign-in for non-institutional domain")
        raise DomainNotAllowedError(
            "This platform is limited to IIUM Live accounts.",
            details={"allowed_domains": settings.allowed_domain_list},
        )

    # -- profile / role -----------------------------------------------------
    result = await db.execute(select(Profile).where(Profile.id == user_uuid))
    profile = result.scalar_one_or_none()

    if profile is None:
        # The auth trigger creates this row on sign-up. A missing row means the
        # trigger was not installed, so refuse rather than guess a role.
        logger.error("No profiles row for authenticated user %s", user_uuid)
        raise AuthenticationError(
            "Your account is not set up on this platform yet.",
            code="profile_missing",
        )

    if not profile.is_active:
        raise AccountDisabledError()

    return AuthenticatedUser(
        id=user_id,
        email=email or profile.email,
        role=profile.role,
        is_admin=profile.role == UserRole.ADMIN,
        profile=profile,
    )
