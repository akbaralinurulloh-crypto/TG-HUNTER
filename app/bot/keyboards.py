"""Keyboards for Telegram management bot."""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Main administrative quick-access reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/status"), KeyboardButton(text="/stats")],
            [KeyboardButton(text="/queue"), KeyboardButton(text="/sources")],
            [KeyboardButton(text="/pause"), KeyboardButton(text="/resume")],
            [KeyboardButton(text="/errors"), KeyboardButton(text="/help")],
        ],
        resize_keyboard=True,
    )
