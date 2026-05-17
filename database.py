"""
Database module - SQLAlchemy async models and initialization
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import (
    Integer, String, Float, Boolean, DateTime, Text, BigInteger, func
)
from datetime import datetime
from typing import AsyncGenerator
from config import settings
import logging

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


class Registration(Base):
    """Interview registration model"""
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serial_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    roll_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    sib: Mapped[str] = mapped_column(String(100), nullable=False)
    date_range: Mapped[str] = mapped_column(String(50), nullable=False)
    introduction: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_date: Mapped[str] = mapped_column(String(100), nullable=False)
    screenshot_file_id: Mapped[str] = mapped_column(String(200), nullable=True)
    screenshot_file_type: Mapped[str] = mapped_column(String(20), nullable=True)  # photo/document
    scheduled_date: Mapped[str] = mapped_column(String(100), nullable=True)
    scheduled_time: Mapped[str] = mapped_column(String(50), nullable=True)
    meet_link: Mapped[str] = mapped_column(String(300), nullable=True)
    interview_type: Mapped[str] = mapped_column(String(20), default="real")  # real/mock
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class MockPayment(Base):
    """Mock interview payment model"""
    __tablename__ = "mock_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    upi_id_used: Mapped[str] = mapped_column(String(100), nullable=False)
    utr_number: Mapped[str] = mapped_column(String(100), nullable=True, unique=True)
    screenshot_file_id: Mapped[str] = mapped_column(String(200), nullable=True)
    payment_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending/approved/declined
    approved_by: Mapped[int] = mapped_column(BigInteger, nullable=True)
    approved_by_name: Mapped[str] = mapped_column(String(100), nullable=True)
    expiry_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PaymentSettings(Base):
    """Dynamic payment settings"""
    __tablename__ = "payment_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AdminSession(Base):
    """Admin login sessions"""
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    logged_in_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AdminAuditLog(Base):
    """Admin audit log"""
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    admin_username: Mapped[str] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database - create tables and default settings"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Insert default payment settings
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        
        defaults = {
            "mock_price": str(settings.DEFAULT_MOCK_PRICE),
            "upi_id": settings.DEFAULT_UPI_ID,
            "payee_name": settings.DEFAULT_PAYEE_NAME,
            "payments_enabled": "true" if settings.PAYMENTS_ENABLED else "false",
        }
        
        for key, value in defaults.items():
            result = await session.execute(
                select(PaymentSettings).where(PaymentSettings.key == key)
            )
            if not result.scalar_one_or_none():
                session.add(PaymentSettings(key=key, value=value))
        
        await session.commit()
    
    logger.info("Database initialized successfully")
