"""
Configuration module - loads all settings from environment variables
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Bot Configuration
    BOT_TOKEN: str
    ADMIN_IDS: str = ""  # Comma-separated admin user IDs
    ADMIN_GROUP_ID: str = ""  # Group/Channel ID for admin notifications
    FORCE_JOIN_CHANNEL: str = ""  # Channel username (e.g. @mychannel) or ID

    # Admin Panel
    ADMIN_PASSWORD: str = "admin123"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///interview_bot.db"

    # Payment Defaults
    DEFAULT_MOCK_PRICE: float = 99.0
    DEFAULT_UPI_ID: str = "example@upi"
    DEFAULT_PAYEE_NAME: str = "Interview Management"
    PAYMENTS_ENABLED: bool = True

    # Payment Timer (minutes)
    PAYMENT_EXPIRY_MINUTES: int = 30

    # Rate Limiting
    RATE_LIMIT_MESSAGES: int = 5
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # Backup
    AUTO_BACKUP_INTERVAL_HOURS: int = 24

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def admin_ids_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

    @property
    def force_join_channel(self) -> str:
        return self.FORCE_JOIN_CHANNEL.strip() if self.FORCE_JOIN_CHANNEL else ""


settings = Settings()
