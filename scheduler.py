"""
Scheduler - handles auto backup and payment expiry cleanup
"""

import logging
import shutil
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update
from database import AsyncSessionLocal, MockPayment
from config import settings

logger = logging.getLogger(__name__)


async def expire_pending_payments():
    """Mark expired pending payments"""
    now = datetime.utcnow()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MockPayment).where(
                MockPayment.payment_status == "pending",
                MockPayment.expiry_at < now,
                MockPayment.expiry_at.isnot(None),
            )
        )
        expired = result.scalars().all()
        for p in expired:
            p.payment_status = "expired"
        if expired:
            await session.commit()
            logger.info(f"Expired {len(expired)} pending payments")


async def auto_backup_database():
    """Create a timestamped backup of the SQLite database"""
    try:
        if "sqlite" not in settings.DATABASE_URL:
            return  # Only for SQLite

        db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        backup_name = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(db_path, backup_name)
        logger.info(f"✅ Database backed up: {backup_name}")
    except Exception as e:
        logger.error(f"Backup failed: {e}")


def setup_scheduler(bot) -> AsyncIOScheduler:
    """Setup and return the async scheduler"""
    scheduler = AsyncIOScheduler()

    # Expire payments every 5 minutes
    scheduler.add_job(
        expire_pending_payments,
        "interval",
        minutes=5,
        id="expire_payments",
    )

    # Auto backup every N hours
    scheduler.add_job(
        auto_backup_database,
        "interval",
        hours=settings.AUTO_BACKUP_INTERVAL_HOURS,
        id="auto_backup",
    )

    return scheduler
