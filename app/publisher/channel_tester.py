import sys
import asyncio
from typing import Dict, Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError, TelegramBadRequest
from app.config import settings
from app.logging_config import logger


class ChannelTester:
    """Verifies Telegram Bot authentication and posting permissions to the target channel."""

    def __init__(self, bot: Optional[Bot] = None):
        self.bot = bot

    async def verify_bot_auth(self) -> Dict[str, Any]:
        """Verify that BOT_TOKEN is valid by calling get_me()."""
        if not self.bot:
            return {"success": False, "error": "Bot instance is not initialized"}
        try:
            bot_info = await self.bot.get_me()
            logger.info(f"Bot authentication successful: @{bot_info.username} (ID: {bot_info.id})")
            return {
                "success": True,
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
            }
        except TelegramUnauthorizedError:
            msg = "BOT_TOKEN noto'g'ri yoki bekor qilingan! Iltimos, @BotFather dan olingan yangi tokenni .env ga yozing."
            logger.error(msg)
            return {"success": False, "error": msg}
        except Exception as e:
            msg = f"Bot autentifikatsiyasida xatolik: {e}"
            logger.error(msg)
            return {"success": False, "error": msg}

    async def check_channel_permissions(self, channel_identifier: Optional[str] = None) -> Dict[str, Any]:
        """Verify bot is admin in the target channel and has permission to post messages."""
        channel = channel_identifier or settings.TARGET_CHANNEL
        if not channel:
            return {"success": False, "error": "TARGET_CHANNEL sozlanmagan!"}

        try:
            bot_info = await self.bot.get_me()
            chat_member = await self.bot.get_chat_member(chat_id=channel, user_id=bot_info.id)
            status = chat_member.status  # "administrator" or "creator"

            clean_ch = channel if channel.startswith("@") else f"@{channel}"
            if status not in ("administrator", "creator"):
                msg = (
                    f"Bot {clean_ch} kanalida administrator emas (joriy status: {status}). "
                    f"Iltimos, kanal sozlamalariga kirib, botni administrator qilib tayinlang!"
                )
                logger.error(msg)
                return {"success": False, "status": status, "error": msg}

            # Check post messages permission
            can_post = getattr(chat_member, "can_post_messages", None)
            if can_post is False:
                msg = f"Bot {clean_ch} kanalida administrator, lekin 'Post Messages' (Xabar yozish) huquqi yo'q!"
                logger.error(msg)
                return {"success": False, "status": status, "can_post": False, "error": msg}

            logger.info(f"Bot {clean_ch} kanalida to'liq xabar joylash huquqiga ega.")
            return {"success": True, "status": status, "can_post": True}

        except TelegramBadRequest as bad_req:
            msg = (
                f"Kanal topilmadi yoki bot kanalga qo'shilmagan: {bad_req}. "
                f"Iltimos, botni @{channel.replace('@', '')} kanaliga administrator qilib qo'shing."
            )
            logger.error(msg)
            return {"success": False, "error": msg}
        except Exception as e:
            msg = f"Kanal huquqlarini tekshirishda xatolik: {e}"
            logger.error(msg)
            return {"success": False, "error": msg}

    async def send_test_ping(self, target_chat_id: Optional[Any] = None) -> Dict[str, Any]:
        """Send diagnostic confirmation directly to admin private chat (NEVER to public channel)."""
        target = target_chat_id or (settings.admin_ids_list[0] if settings.admin_ids_list else None)
        if not target:
            return {"success": False, "error": "Admin ID sozlanmagan!"}
        text = (
            "🤖 <b>Muhtasham Telegram AI Agent</b>\n\n"
            "✅ <i>Tizim ulanishi va kanal huquqlari muvaffaqiyatli sinovdan o'tkazildi.</i>\n"
            f"📡 <b>Maqsadli kanal:</b> <code>{settings.TARGET_CHANNEL}</code>\n"
            f"📅 <b>Vaqt:</b> <code>Asia/Tashkent</code>"
        )
        try:
            sent_msg = await self.bot.send_message(
                chat_id=target,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            logger.info(f"Test xabari faqat adminga ({target}) muvaffaqiyatli yuborildi! Xabar ID: {sent_msg.message_id}")
            return {"success": True, "message_id": sent_msg.message_id}
        except Exception as e:
            msg = f"Admin test xabarini yuborishda xatolik: {e}"
            logger.error(msg)
            return {"success": False, "error": msg}


async def run_channel_diagnostic(bot: Optional[Bot] = None) -> bool:
    """Run full diagnostic sequence for Phase 1/Section 17 (Alerts sent only to Admin)."""
    missing = settings.validate_required_settings()
    if missing:
        logger.warning(f"Majburiy sozlamalar to'ldirilmagan: {', '.join(missing)}")
        print("\n" + "=" * 60)
        print("  DIAGNOSTIKA OGOHLANTIRISHI: Maxfiy sozlamalar kiritilmagan")
        print("=" * 60)
        print(f"Quyidagi parametrlar .env faylida kiritilishi shart: {', '.join(missing)}")
        print("Foydalanish: .env.example faylidan nusxa olib, to'ldiring.\n")
        return False

    bot_instance = bot or Bot(token=settings.BOT_TOKEN)
    tester = ChannelTester(bot=bot_instance)

    try:
        # 1. Bot token check
        auth_res = await tester.verify_bot_auth()
        if not auth_res["success"]:
            print(f"\n❌ Bot autentifikatsiyasi muvaffaqiyatsiz: {auth_res['error']}\n")
            return False

        # 2. Permissions check for each configured target channel (DO NOT post to channel!)
        channels_to_test = settings.target_channels_list or [settings.TARGET_CHANNEL]
        success_channels = []
        failed_channels = []

        for ch in channels_to_test:
            print(f"\n--- Kanal ruxsati tekshirilmoqda: {ch} ---")
            perm_res = await tester.check_channel_permissions(ch)
            if not perm_res["success"]:
                print(f"❌ Kanal ruxsati yetarli emas ({ch}): {perm_res['error']}")
                failed_channels.append((ch, perm_res['error']))
                continue

            print(f"✅ {ch} ulanishi va xabar joylash huquqi tasdiqlandi!")
            success_channels.append(ch)

        # 3. Send test confirmation ONLY to admin private chat (NEVER to public channel)
        if success_channels:
            for admin_id in settings.admin_ids_list:
                try:
                    await tester.send_test_ping(target_chat_id=admin_id)
                except Exception as e:
                    logger.warning(f"Admin {admin_id} ga bildirishnoma yetib bormadi: {e}")

        print("\n" + "=" * 60)
        if success_channels:
            print("  ✅ KANAL RUXSATLARI MUVAFFAQIYATLI TASDIQLANDI!")
            for ch in success_channels:
                print(f"  • {ch}: Xabar joylash huquqi mavjud")
        if failed_channels:
            print("  ⚠️ BAZI KANALLARDA XATOLIK ANIQLANDI:")
            for ch, err in failed_channels:
                print(f"  • {ch}: {err}")
        print("=" * 60 + "\n")

        return len(success_channels) > 0

    finally:
        if not bot:
            await bot_instance.session.close()


if __name__ == "__main__":
    asyncio.run(run_channel_diagnostic())
