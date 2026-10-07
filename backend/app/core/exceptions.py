"""Domain exceptions and their mapping onto HTTP responses.

The API returns one consistent envelope for every failure:

    {
      "error": {
        "code": "resource_not_found",
        "message": "That resource could not be found.",
        "details": {...},            # optional, safe for the client
        "request_id": "9f2c..."
      }
    }

`message` is always safe to show a user. Internal detail -- stack traces,
third-party payloads, connection strings -- stays in the logs only.
"""

from __future__ import annotations

from typing import Any


class SMAReXError(Exception):
    """Base class for every error the application raises deliberately."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "Something went wrong. Please try again."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        super().__init__(self.message)

    def to_payload(self, request_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        if request_id:
            payload["request_id"] = request_id
        return {"error": payload}


# ---------------------------------------------------------------------------
# 400 / 422 -- the caller sent something we cannot accept
# ---------------------------------------------------------------------------
class ValidationError(SMAReXError):
    status_code = 422
    code = "validation_error"
    message = "Some of the submitted values are not valid."


class InvalidFileError(SMAReXError):
    status_code = 415
    code = "invalid_file"
    message = "That file is not a valid PDF."


class FileTooLargeError(SMAReXError):
    status_code = 413
    code = "file_too_large"
    message = "That file is larger than the upload limit."


class DomainNotAllowedError(SMAReXError):
    status_code = 403
    code = "domain_not_allowed"
    message = "Only institutional IIUM Live accounts may use SMAReX."


# ---------------------------------------------------------------------------
# 401 / 403 -- identity and authorisation
# ---------------------------------------------------------------------------
class AuthenticationError(SMAReXError):
    status_code = 401
    code = "unauthenticated"
    message = "Please sign in to continue."


class AuthorizationError(SMAReXError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action."


class AccountDisabledError(SMAReXError):
    status_code = 403
    code = "account_disabled"
    message = "This account has been suspended. Contact an administrator."


# ---------------------------------------------------------------------------
# 404 / 409 -- resource lifecycle
# ---------------------------------------------------------------------------
class NotFoundError(SMAReXError):
    status_code = 404
    code = "not_found"
    message = "The requested item could not be found."


class ConflictError(SMAReXError):
    status_code = 409
    code = "conflict"
    message = "That action conflicts with the current state of the resource."


# ---------------------------------------------------------------------------
# Security pipeline
# ---------------------------------------------------------------------------
class MaliciousFileError(SMAReXError):
    status_code = 422
    code = "malicious_file_rejected"
    message = (
        "This file was flagged as unsafe and has not been stored. "
        "It was not published and no other user can access it."
    )


class SuspiciousFileError(SMAReXError):
    status_code = 422
    code = "suspicious_file_rejected"
    message = (
        "This file needs a security review before it can be shared. "
        "It has been held for an administrator."
    )


class SecurityScanError(SMAReXError):
    status_code = 503
    code = "security_scan_unavailable"
    message = "The security scanner is unavailable, so the upload was not stored."


# ---------------------------------------------------------------------------
# 5xx -- infrastructure
# ---------------------------------------------------------------------------
class StorageError(SMAReXError):
    status_code = 502
    code = "storage_error"
    message = "The file store could not be reached. Please try again."


class DatabaseError(SMAReXError):
    status_code = 503
    code = "database_error"
    message = "The database is unavailable. Please try again shortly."


class UpstreamServiceError(SMAReXError):
    status_code = 502
    code = "upstream_service_error"
    message = "A third-party service did not respond as expected."


class SummaryGenerationError(SMAReXError):
    """Never propagated to the caller: the file is already stored safely.

    The pipeline catches this, marks ``ai_summary_status = 'failed'`` and still
    publishes the resource.
    """

    status_code = 500
    code = "summary_generation_failed"
    message = "The summary could not be generated for this document."