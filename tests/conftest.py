"""Pytest configuration and async test fixtures using SQLite in-memory."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database.models import Base
from app.database.session import set_engine_and_session
from app.config import settings


@pytest_asyncio.fixture
async def test_engine():
    """Create in-memory async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    set_engine_and_session(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provide transactional async session for tests."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_admin_ids(monkeypatch):
    """Mock admin list with known test ID."""
    monkeypatch.setattr(settings, "ADMIN_IDS", "999888111,555444333")
    return [999888111, 555444333]
