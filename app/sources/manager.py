"""Source management and copyright/rights enforcement (TZ Section 5 & 6)."""
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Source, SystemLog
from app.logging_config import logger


class SourceManager:
    """Manages content sources, active status, and verified copyright/usage rights."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_sources(self) -> List[Source]:
        """Fetch all active sources configured in the database."""
        stmt = select(Source).where(Source.active.is_(True)).order_by(Source.id.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_source_by_identifier(self, identifier: str) -> Optional[Source]:
        """Fetch source by telegram identifier (e.g. 'MuhtashamUmra')."""
        clean_ident = identifier.replace("https://t.me/", "").replace("@", "").split("?")[0].strip()
        stmt = select(Source).where(Source.telegram_identifier == clean_ident)
        return (await self.session.execute(stmt)).scalars().first()

    async def check_usage_rights(self, source_identifier: str) -> Dict[str, Any]:
        """
        Check if the source has verified usage rights for auto-publishing (TZ Section 6).
        Returns {'allowed': bool, 'status': str, 'notes': str}.
        """
        src = await self.get_source_by_identifier(source_identifier)
        if not src:
            return {
                "allowed": False,
                "status": "UNKNOWN",
                "notes": f"Manba @{source_identifier} bazada ro'yxatdan o'tmagan",
            }

        if not src.active:
            return {
                "allowed": False,
                "status": "INACTIVE",
                "notes": f"Manba @{source_identifier} faol emas",
            }

        is_verified = (src.rights_status == "VERIFIED")
        return {
            "allowed": is_verified,
            "status": src.rights_status,
            "notes": src.rights_notes or "",
        }

    async def register_source(
        self,
        identifier: str,
        title: str,
        rights_status: str = "VERIFIED",
        rights_notes: Optional[str] = "Muhtasham Travel rasmiy/kelishilgan manbasi",
        active: bool = True,
    ) -> Source:
        """Register or update a source with legal usage rights status."""
        clean_ident = identifier.replace("https://t.me/", "").replace("@", "").split("?")[0].strip()
        existing = await self.get_source_by_identifier(clean_ident)
        if existing:
            existing.title = title
            existing.rights_status = rights_status
            existing.rights_notes = rights_notes
            existing.active = active
            await self.session.commit()
            return existing

        new_src = Source(
            telegram_identifier=clean_ident,
            title=title,
            rights_status=rights_status,
            rights_notes=rights_notes,
            active=active,
        )
        self.session.add(new_src)
        await self.session.commit()
        logger.info(f"Yangi manba ro'yxatga olindi: @{clean_ident} (Huquq: {rights_status})")
        return new_src

    async def seed_initial_sources(self):
        """Seed the approved Umrah sources."""
        initial = [
            ("MuhtashamUmra", "Muhtasham Umra", "VERIFIED", "Muhtasham brendi rasmiy kanali"),
            ("nurlisafar", "Nurli Safar", "VERIFIED", "Hamkor ziyorat kanali — ruxsat berilgan"),
            ("muhtashamtravel", "Muhtasham Travel", "VERIFIED", "Muhtasham Travel asosiy ziyorat kanali"),
            ("Muhtashamtravel_umra_sari_1", "Muhtasham Travel Umra Sari 1", "VERIFIED", "Muhtasham brendi rasmiy kanali"),
        ]
        for ident, title, rights, notes in initial:
            await self.register_source(ident, title, rights, notes)
