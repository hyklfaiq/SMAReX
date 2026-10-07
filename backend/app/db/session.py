"""Async SQLAlchemy engine, session factory and the request-scoped session."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    kwargs: dict = {"echo": settings.db_echo, "future": True, "pool_pre_ping": True}

    url = settings.database_url

    # Supabase's Transaction Pooler (pgbouncer in transaction mode, port 6543)
    # hands out a fresh backend connection per transaction, so a named prepared
    # statement created on one connection is already gone on the next. asyncpg
    # then fails with DuplicatePreparedStatementError. Disabling its statement
    # cache and using NullPool is the supported combination for that mode.
    if ":6543" in url:
        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = {
            "statement_cache_size": 0,
            "server_settings": {"application_name": "smarex-api"},
        }
    elif ":5432" in url:
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )
    else:
        # Unknown host/port: assume a pooler and stay conservative.
        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = {
            "statement_cache_size": 0,
            "server_settings": {"application_name": "smarex-api"},
        }

    return create_async_engine(url, **kwargs)


def get_engine() -> AsyncEngine:
    """Lazily created process-wide engine."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
        logger.info("Database engine created")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Standalone transactional scope for background work and scripts."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency. Commits on success, rolls back on any exception."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Called on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        logger.info("Database engine disposed")
    _engine = None
    _session_factory = None