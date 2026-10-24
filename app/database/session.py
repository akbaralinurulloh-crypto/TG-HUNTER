"""Database engine and async session management."""
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from app.config import settings
from app.logging_config import logger

is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine_kwargs = {}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 60.0}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    **engine_kwargs
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def set_engine_and_session(custom_engine: AsyncEngine):
    """Set custom engine and sessionmaker (for testing with SQLite in-memory)."""
    global engine, AsyncSessionLocal
    engine = custom_engine
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async database session context."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session rollback: {e}")
            raise
        finally:
            await session.close()


async def init_database(custom_engine: AsyncEngine = None) -> None:
    """Create all tables defined in models and configure SQLite WAL mode."""
    from sqlalchemy import text
    from app.database.models import Base
    target_engine = custom_engine or engine
    logger.info("Initializing database schema...")
    async with target_engine.begin() as conn:
        if is_sqlite:
            try:
                await conn.execute(text("PRAGMA journal_mode=WAL;"))
                await conn.execute(text("PRAGMA busy_timeout=60000;"))
            except Exception as e:
                logger.warning(f"Could not enable WAL mode: {e}")
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema initialized with WAL mode.")
