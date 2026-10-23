"""Public Telegram channel web preview scraper (https://t.me/s/<channel>).

Enables automatic 24/7 content collection from public Telegram channels
without requiring user account credentials or MTProto session strings.
"""
import os
import re
import asyncio
from typing import List, Optional, Dict, Any
import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.logging_config import logger
from app.sources.manager import SourceManager
from app.sources.collector import ContentCollector
from app.services.orchestrator import ContentPipelineService


class TelegramWebScraper:
    """Scrapes public Telegram channels via web preview interface."""

    def __init__(self, bot=None):
        self.bot = bot
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "uz,en-US,en;q=0.9,ru;q=0.8",
        }
        os.makedirs(settings.MEDIA_TEMP_DIR, exist_ok=True)

    async def fetch_channel_html(self, session: aiohttp.ClientSession, channel_ident: str) -> Optional[str]:
        """Fetch HTML content from https://t.me/s/<channel_ident>."""
        url = f"https://t.me/s/{channel_ident}"
        try:
            async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    logger.warning(f"Could not fetch {url}: HTTP {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching channel {channel_ident}: {e}")
            return None

    async def download_media(self, session: aiohttp.ClientSession, media_url: str, filename: str) -> Optional[str]:
        """Download media file locally into MEDIA_TEMP_DIR."""
        if not media_url:
            return None
        target_path = os.path.join(settings.MEDIA_TEMP_DIR, filename)
        if os.path.exists(target_path):
            return target_path

        try:
            async with session.get(media_url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    with open(target_path, "wb") as f:
                        f.write(data)
                    return target_path
        except Exception as e:
            logger.warning(f"Could not download media from {media_url}: {e}")
        return None

    def parse_messages(self, html: str, channel_ident: str) -> List[Dict[str, Any]]:
        """Parse Telegram web preview HTML into structured post items."""
        soup = BeautifulSoup(html, "html.parser")
        items = []

        message_divs = soup.find_all("div", class_="tgme_widget_message")
        for mdiv in message_divs:
            data_post = mdiv.get("data-post", "")
            if not data_post or "/" not in data_post:
                continue

            try:
                msg_id = int(data_post.split("/")[-1])
            except ValueError:
                continue

            # Extract text
            text_elem = mdiv.find("div", class_="tgme_widget_message_text")
            text = text_elem.get_text(separator="\n").strip() if text_elem else ""

            # Extract photo
            photo_url = None
            photo_wrap = mdiv.find("a", class_="tgme_widget_message_photo_wrap")
            if photo_wrap:
                style = photo_wrap.get("style", "")
                m = re.search(r"url\('(.*?)'\)", style)
                if m:
                    photo_url = m.group(1)

            # Extract video
            video_url = None
            video_elem = mdiv.find("video")
            if video_elem:
                video_url = video_elem.get("src")

            media_type = "TEXT"
            media_url = None
            if photo_url:
                media_type = "PHOTO"
                media_url = photo_url
            elif video_url:
                media_type = "VIDEO"
                media_url = video_url

            # Skip messages with neither text nor media
            if not text and not media_url:
                continue

            items.append({
                "source_identifier": channel_ident,
                "message_id": msg_id,
                "text": text,
                "media_type": media_type,
                "media_url": media_url,
            })

        return items

    async def scrape_and_process_channel(
        self,
        db_session: AsyncSession,
        http_session: aiohttp.ClientSession,
        channel_ident: str,
    ) -> int:
        """Scrape a single channel, download media, ingest and process posts through pipeline."""
        clean_ident = channel_ident.replace("https://t.me/", "").replace("@", "").split("?")[0].strip()
        html = await self.fetch_channel_html(http_session, clean_ident)
        if not html:
            return 0

        raw_posts = self.parse_messages(html, clean_ident)
        if not raw_posts:
            return 0

        collector = ContentCollector(db_session)
        pipeline = ContentPipelineService(db_session, bot=self.bot)
        newly_processed = 0

        # Process from oldest to newest in current page
        for p in raw_posts:
            media_ref = None
            if p["media_url"]:
                ext = "mp4" if p["media_type"] == "VIDEO" else "jpg"
                filename = f"{clean_ident}_{p['message_id']}.{ext}"
                media_ref = await self.download_media(http_session, p["media_url"], filename)

            # Ingest post into source_posts table
            source_post = await collector.ingest_post(
                source_identifier=clean_ident,
                source_message_id=p["message_id"],
                original_text=p["text"],
                media_type=p["media_type"],
                media_reference=media_ref,
            )

            # If it's a new post (not previously ingested), run through pipeline
            if source_post:
                try:
                    await pipeline.process_source_post(source_post)
                    newly_processed += 1
                except Exception as e:
                    logger.error(f"Error processing post {clean_ident} #{p['message_id']}: {e}")

        return newly_processed

    async def scrape_all_active_sources(self, db_session: AsyncSession) -> int:
        """Scrape all active sources configured in the database."""
        mgr = SourceManager(db_session)
        sources = await mgr.get_active_sources()
        if not sources:
            logger.warning("No active sources found in database to scrape.")
            return 0

        total_new = 0
        async with aiohttp.ClientSession() as http_session:
            for src in sources:
                try:
                    cnt = await self.scrape_and_process_channel(
                        db_session,
                        http_session,
                        src.telegram_identifier,
                    )
                    total_new += cnt
                except Exception as e:
                    logger.error(f"Error scraping source {src.telegram_identifier}: {e}")

        logger.info(f"Sources scraping finished. Total new posts ingested: {total_new}")
        return total_new
