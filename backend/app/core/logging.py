"""Logging setup and the correlation-id middleware.

Each request is assigned an id that appears in the response header, in every
log line for that request, and in error payloads, so a user-reported failure
can be traced end to end without exposing internals to the browser.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("smarex")


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure the root logger once, at application start-up."""
    handler = logging.StreamHandler(sys.stdout)

    if json_output:
        from pythonjsonlogger import jsonlogger  # optional dependency

        handler.setFormatter(
            jsonlogger.JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
            )
        )
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Third-party noise reduction
    for noisy in ("httpx", "httpcore", "asyncio", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestContextFilter(logging.Filter):
    """Injects the active request id into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def get_logger(name: str) -> logging.Logger:
    """Module level helper: ``logger = get_logger(__name__)``."""
    log = logging.getLogger(name)
    if not any(isinstance(f, RequestContextFilter) for f in log.filters):
        log.addFilter(RequestContextFilter())
    return log


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns ``X-Request-ID``, records latency, logs unhandled failures."""

    def __init__(self, app, slow_request_ms: int = 2000) -> None:
        super().__init__(app)
        self.slow_request_ms = slow_request_ms

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get("x-request-id")
        rid = incoming if incoming and len(incoming) <= 64 else uuid.uuid4().hex
        token = request_id_var.set(rid)
        request.state.request_id = rid
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - started) * 1000
            get_logger("smarex.request").exception(
                "Unhandled error on %s %s after %.0fms",
                request.method,
                request.url.path,
                elapsed,
            )
            request_id_var.reset(token)
            raise

        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = rid
        response.headers["X-Process-Time-Ms"] = f"{elapsed:.0f}"

        level = logging.WARNING if elapsed > self.slow_request_ms else logging.INFO
        get_logger("smarex.request").log(
            level,
            "%s %s -> %d (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        request_id_var.reset(token)
        return response