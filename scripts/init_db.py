"""Database initialization and initial seeding script for Umrah Agent."""
import asyncio
from app.database.session import init_database, get_db
from app.database.models import SystemState
from app.sources.manager import SourceManager
from app.logging_config import logger


async def seed_database():
    """Create all tables and register initial approved Umrah sources."""
    logger.info("Initializing database schema...")
    await init_database()

    async with get_db() as session:
        # Seed initial sources
        mgr = SourceManager(session)
        await mgr.seed_initial_sources()

        # Seed initial system flags
        state = await session.get(SystemState, "is_paused")
        if not state:
            state = SystemState(key="is_paused", value="false")
            session.add(state)
            logger.info("Initialized system state: is_paused=false")

        await session.commit()
    logger.info("Database seeding completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed_database())
