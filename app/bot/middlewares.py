"""Bot filters and security middlewares (TZ Section 12 & 15)."""
from aiogram import types
from aiogram.filters import BaseFilter
from app.config import settings
from app.logging_config import logger


class IsAdminFilter(BaseFilter):
    """Restricts command and callback execution strictly to authorized administrators."""

    async def __call__(self, event: types.TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        return settings.is_admin(user.id)
