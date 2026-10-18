"""Bot package exports."""
from aiogram import Bot, Dispatcher
from app.bot.handlers import router as admin_router
from app.bot.middlewares import IsAdminFilter
from app.bot.keyboards import get_admin_main_menu


def setup_dispatcher() -> Dispatcher:
    """Setup and configure aiogram Dispatcher with admin router."""
    dp = Dispatcher()
    dp.include_router(admin_router)
    return dp


__all__ = ["setup_dispatcher", "admin_router", "IsAdminFilter", "get_admin_main_menu"]
