"""Application configuration using Pydantic Settings."""
import os
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 1. Telegram Bot (aiogram 3) & Channel
    BOT_TOKEN: str = Field(default="", description="Telegram Bot Token from @BotFather")
    ADMIN_IDS: Union[str, int, List[int]] = Field(
        default="",
        description="Comma-separated Telegram IDs of authorized administrators",
    )
    TARGET_CHANNEL: str = Field(
        default="@muhtashamtraveluzz",
        description="Target Telegram channel username or ID where approved posts are published",
    )

    # 2. Database (PostgreSQL)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/muhtasham_db",
        description="Async database connection URL",
    )

    # 3. AI Provider (Gemini / OpenAI)
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")
    AI_MODEL_NAME: str = Field(default="gemini-3.5-flash", description="AI Model Name")
    OPENAI_API_KEY: str = Field(default="", description="Optional OpenAI API Key")

    # 4. Scheduling & Limits (Asia/Tashkent)
    TIMEZONE: str = Field(default="Asia/Tashkent", description="Timezone for scheduler")
    DAILY_POST_MIN: int = Field(default=20, description="Minimum daily target posts")
    DAILY_POST_MAX: int = Field(default=50, description="Maximum daily target posts")
    PUBLISH_START_HOUR: int = Field(default=7, description="Publishing window start hour (7:00)")
    PUBLISH_END_HOUR: int = Field(default=23, description="Publishing window end hour (23:00)")
    REPORT_HOURS: Union[str, int, List[int]] = Field(default="8,13,20", description="Daily report hours")

    # 5. Telegram MTProto (Optional, for source channels monitoring)
    TELEGRAM_API_ID: int = Field(default=0, description="Telegram API ID from my.telegram.org")
    TELEGRAM_API_HASH: str = Field(default="", description="Telegram API Hash")
    TELETHON_SESSION_STRING: str = Field(default="", description="Telethon StringSession token")

    # 6. Deduplication, Storage & Contacts
    MEDIA_TEMP_DIR: str = Field(default="./temp_media", description="Temporary media directory")
    PHASH_THRESHOLD: int = Field(default=5, description="Max Hamming distance for duplicate images")
    SEMANTIC_THRESHOLD: float = Field(default=0.75, description="Semantic similarity threshold")
    LOG_LEVEL: str = Field(default="INFO", description="Log level")
    CONTACT_PHONE: str = Field(default="+998 88 832 77 00", description="Contact phone appended to published posts")

    @property
    def admin_ids_list(self) -> List[int]:
        """Return list of authorized admin IDs as integers."""
        if isinstance(self.ADMIN_IDS, int):
            return [self.ADMIN_IDS]
        if isinstance(self.ADMIN_IDS, list):
            return [int(x) for x in self.ADMIN_IDS]
        if not self.ADMIN_IDS or not str(self.ADMIN_IDS).strip():
            return []
        ids = []
        for part in str(self.ADMIN_IDS).split(","):
            part = part.strip()
            if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
                ids.append(int(part))
        return ids

    @property
    def report_hours_list(self) -> List[int]:
        """Return list of hours for scheduled reports."""
        if isinstance(self.REPORT_HOURS, int):
            return [self.REPORT_HOURS]
        if isinstance(self.REPORT_HOURS, list):
            return [int(x) for x in self.REPORT_HOURS]
        hours = []
        for h in str(self.REPORT_HOURS).split(","):
            h = h.strip()
            if h.isdigit():
                hours.append(int(h))
        return hours or [8, 13, 20]

    @property
    def target_channels_list(self) -> List[str]:
        """Return list of target channels normalized as @username or chat ID."""
        if not self.TARGET_CHANNEL or not str(self.TARGET_CHANNEL).strip():
            return []
        import re
        raw_items = re.split(r'[\r\n,]+', str(self.TARGET_CHANNEL).strip())
        channels = []
        for raw in raw_items:
            raw = raw.strip()
            if not raw:
                continue
            if "t.me/" in raw:
                raw = raw.split("t.me/")[-1].strip().split("/")[0].split("?")[0]
            if raw and not raw.startswith("@") and not raw.startswith("-100") and not (raw.startswith("-") and raw[1:].isdigit()):
                raw = f"@{raw}"
            if raw and raw not in channels:
                channels.append(raw)
        return channels

    def is_admin(self, user_id: int) -> bool:
        """Check if user_id is in the authorized admin list."""
        return user_id in self.admin_ids_list

    def validate_required_settings(self) -> List[str]:
        """Validate required settings and return list of missing keys."""
        missing = []
        if not self.BOT_TOKEN or self.BOT_TOKEN.startswith("1234567890:"):
            missing.append("BOT_TOKEN")
        if not self.admin_ids_list:
            missing.append("ADMIN_IDS")
        if not self.TARGET_CHANNEL:
            missing.append("TARGET_CHANNEL")
        return missing


settings = Settings()
