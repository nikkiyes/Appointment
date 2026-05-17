"""
Middlewares - Rate limiting and force channel join
"""

import logging
import time
from typing import Callable, Dict, Any, Awaitable
from collections import defaultdict
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import settings

logger = logging.getLogger(__name__)

# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class RateLimitMiddleware(BaseMiddleware):
    """Limits messages per user per time window"""

    def __init__(self):
        self.user_timestamps: Dict[int, list] = defaultdict(list)
        self.limit = settings.RATE_LIMIT_MESSAGES
        self.window = settings.RATE_LIMIT_WINDOW

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id:
            now = time.time()
            timestamps = self.user_timestamps[user_id]
            # Remove old timestamps outside window
            self.user_timestamps[user_id] = [
                t for t in timestamps if now - t < self.window
            ]
            if len(self.user_timestamps[user_id]) >= self.limit:
                if isinstance(event, Message):
                    await event.answer(
                        "⚠️ You're sending messages too fast. Please slow down."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "⚠️ Too many requests. Please wait a moment.",
                        show_alert=True
                    )
                return
            self.user_timestamps[user_id].append(now)

        return await handler(event, data)


# ─── Channel Check Middleware ─────────────────────────────────────────────────

EXCLUDED_CALLBACKS = {"check_join", "cancel", "home"}
EXCLUDED_COMMANDS = {"/start", "/admin"}


class ChannelCheckMiddleware(BaseMiddleware):
    """Force users to join channel before using bot"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.channel = settings.force_join_channel
        # Cache of user join status (user_id -> bool)
        self._cache: Dict[int, bool] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Skip if no channel configured
        if not self.channel:
            return await handler(event, data)

        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
            # Skip for admin commands
            if event.text and any(event.text.startswith(cmd) for cmd in EXCLUDED_COMMANDS):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            # Skip check_join callback itself
            if event.data in EXCLUDED_CALLBACKS:
                return await handler(event, data)

        if user_id and not await self._check_membership(user_id):
            from keyboards import join_channel_keyboard
            channel_link = (
                f"https://t.me/{self.channel.lstrip('@')}"
                if self.channel.startswith("@")
                else self.channel
            )
            msg_text = (
                "👋 <b>Welcome!</b>\n\n"
                "To use this bot, you must first join our official channel.\n\n"
                "📢 Click the button below to join, then click <b>I've Joined</b>."
            )
            if isinstance(event, Message):
                await event.answer(msg_text, reply_markup=join_channel_keyboard(channel_link))
            elif isinstance(event, CallbackQuery):
                await event.message.answer(
                    msg_text, reply_markup=join_channel_keyboard(channel_link)
                )
                await event.answer()
            return

        return await handler(event, data)

    async def _check_membership(self, user_id: int) -> bool:
        try:
            member = await self.bot.get_chat_member(self.channel, user_id)
            is_member = member.status not in ("left", "kicked", "banned")
            self._cache[user_id] = is_member
            return is_member
        except Exception as e:
            logger.warning(f"Could not check membership for {user_id}: {e}")
            return True  # Allow if check fails
