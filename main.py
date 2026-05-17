#!/usr/bin/env python3
"""
Interview Management Bot - Main Entry Point
Production-ready Telegram bot for managing interview bookings and mock interviews
"""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database import init_db
from handlers import start_handler
from handlers import booking_handler
from handlers import mock_interview_handler
from handlers import admin_handler
from handlers import payment_handler
from handlers import channel_handler
from middlewares import RateLimitMiddleware, ChannelCheckMiddleware
from scheduler import setup_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    """Main bot startup function"""
    logger.info("🚀 Starting Interview Management Bot...")

    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")

    # Initialize bot with HTML parse mode
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Initialize dispatcher with memory storage
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register middlewares
    dp.message.middleware(RateLimitMiddleware())
    dp.callback_query.middleware(RateLimitMiddleware())
    dp.message.middleware(ChannelCheckMiddleware(bot))

    # Register routers
    dp.include_router(channel_handler.router)
    dp.include_router(start_handler.router)
    dp.include_router(booking_handler.router)
    dp.include_router(mock_interview_handler.router)
    dp.include_router(payment_handler.router)
    dp.include_router(admin_handler.router)

    # Setup scheduler for auto backup and payment expiry
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("✅ Scheduler started")

    # Start polling
    try:
        logger.info("✅ Bot is running. Press Ctrl+C to stop.")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
