"""
Utility functions - serial numbers, QR codes, CSV export, formatting
"""

import csv
import io
import qrcode
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, func
from database import AsyncSessionLocal, Registration, MockPayment, PaymentSettings

logger = logging.getLogger(__name__)


# ─── Serial Number ────────────────────────────────────────────────────────────

async def generate_serial_number() -> str:
    """Generate unique serial number: IM-2024-0001"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count(Registration.id))
        )
        count = result.scalar() or 0
        year = datetime.utcnow().year
        serial = f"IM-{year}-{str(count + 1).zfill(4)}"
        return serial


# ─── Payment Settings ─────────────────────────────────────────────────────────

async def get_payment_setting(key: str) -> Optional[str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PaymentSettings).where(PaymentSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else None


async def set_payment_setting(key: str, value: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PaymentSettings).where(PaymentSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            session.add(PaymentSettings(key=key, value=value))
        await session.commit()


async def get_all_payment_settings() -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PaymentSettings))
        settings_list = result.scalars().all()
        return {s.key: s.value for s in settings_list}


# ─── QR Code ─────────────────────────────────────────────────────────────────

def generate_upi_qr(upi_id: str, payee_name: str, amount: float) -> bytes:
    """Generate UPI QR code as bytes"""
    upi_link = f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount:.2f}&cu=INR"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_link)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read(), upi_link


# ─── CSV Export ───────────────────────────────────────────────────────────────

async def export_registrations_csv(date_range: Optional[str] = None) -> bytes:
    """Export registrations to CSV"""
    async with AsyncSessionLocal() as session:
        query = select(Registration).order_by(Registration.created_at)
        if date_range:
            query = query.where(Registration.date_range == date_range)
        
        result = await session.execute(query)
        registrations = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Serial Number", "Full Name", "Roll Number", "SIB",
        "Date Range", "Preferred Date", "Introduction",
        "Telegram Username", "User ID", "Scheduled Date",
        "Scheduled Time", "Meet Link", "Interview Type", "Registered At"
    ])
    
    for reg in registrations:
        writer.writerow([
            reg.serial_number,
            reg.full_name,
            reg.roll_number,
            reg.sib,
            reg.date_range,
            reg.preferred_date,
            reg.introduction,
            f"@{reg.username}" if reg.username else "N/A",
            reg.user_id,
            reg.scheduled_date or "Not Scheduled",
            reg.scheduled_time or "Not Scheduled",
            reg.meet_link or "Not Provided",
            reg.interview_type,
            reg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])
    
    return output.getvalue().encode("utf-8-sig")


async def export_payments_csv() -> bytes:
    """Export payment records to CSV"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MockPayment).order_by(MockPayment.created_at)
        )
        payments = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "ID", "Full Name", "Username", "Amount", "UPI ID Used",
        "UTR Number", "Payment Status", "Approved By",
        "Payment Time", "Updated At"
    ])
    
    for p in payments:
        writer.writerow([
            p.id,
            p.full_name or "N/A",
            f"@{p.username}" if p.username else "N/A",
            f"₹{p.amount:.2f}",
            p.upi_id_used,
            p.utr_number or "N/A",
            p.payment_status.upper(),
            p.approved_by_name or "N/A",
            p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            p.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])
    
    return output.getvalue().encode("utf-8-sig")


async def export_today_interviews_csv() -> bytes:
    """Export today's scheduled interviews"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Registration)
            .where(Registration.scheduled_date == today)
            .order_by(Registration.scheduled_time)
        )
        interviews = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Metadata
    writer.writerow([f"Today's Interview List - {today}"])
    writer.writerow([f"Total Students: {len(interviews)}"])
    writer.writerow([f"Export Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"])
    writer.writerow([])
    
    writer.writerow([
        "Serial Number", "Student Name", "Roll Number", "SIB",
        "Scheduled Time", "Google Meet Link", "Contact Username",
        "Interview Type"
    ])
    
    for reg in interviews:
        writer.writerow([
            reg.serial_number,
            reg.full_name,
            reg.roll_number,
            reg.sib,
            reg.scheduled_time or "TBD",
            reg.meet_link or "Not Provided",
            f"@{reg.username}" if reg.username else str(reg.user_id),
            reg.interview_type.upper(),
        ])
    
    return output.getvalue().encode("utf-8-sig")


async def export_introductions_csv() -> bytes:
    """Export all introductions"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Registration).order_by(Registration.serial_number)
        )
        registrations = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Serial Number", "Full Name", "Roll Number", "Introduction"])
    
    for reg in registrations:
        writer.writerow([
            reg.serial_number,
            reg.full_name,
            reg.roll_number,
            reg.introduction,
        ])
    
    return output.getvalue().encode("utf-8-sig")


# ─── Message Formatting ───────────────────────────────────────────────────────

def format_registration_summary(data: dict) -> str:
    """Format registration data for confirmation message"""
    return (
        f"<b>📋 Registration Summary</b>\n\n"
        f"👤 <b>Full Name:</b> {data.get('full_name', 'N/A')}\n"
        f"🔢 <b>Roll Number:</b> {data.get('roll_number', 'N/A')}\n"
        f"🏫 <b>SIB:</b> {data.get('sib', 'N/A')}\n"
        f"📅 <b>Date Range:</b> {data.get('date_range', 'N/A')}\n"
        f"📆 <b>Preferred Date:</b> {data.get('preferred_date', 'N/A')}\n\n"
        f"📝 <b>Introduction:</b>\n{data.get('introduction', 'N/A')[:500]}{'...' if len(data.get('introduction', '')) > 500 else ''}\n\n"
        f"📎 <b>Screenshot:</b> {'✅ Uploaded' if data.get('screenshot_file_id') else '❌ Not uploaded'}"
    )


def format_admin_registration(reg: Registration) -> str:
    """Format registration for admin notification"""
    return (
        f"🆕 <b>New Interview Registration</b>\n"
        f"{'─' * 30}\n"
        f"🔖 <b>Serial:</b> <code>{reg.serial_number}</code>\n"
        f"👤 <b>Name:</b> {reg.full_name}\n"
        f"🔢 <b>Roll No:</b> <code>{reg.roll_number}</code>\n"
        f"🏫 <b>SIB:</b> {reg.sib}\n"
        f"📅 <b>Date Range:</b> {reg.date_range}\n"
        f"📆 <b>Preferred Date:</b> {reg.preferred_date}\n"
        f"🐦 <b>Username:</b> @{reg.username or 'N/A'}\n"
        f"🆔 <b>User ID:</b> <code>{reg.user_id}</code>\n"
        f"⏰ <b>Registered:</b> {reg.created_at.strftime('%d %b %Y %H:%M')} UTC\n"
        f"{'─' * 30}\n"
        f"📝 <b>Introduction:</b>\n{reg.introduction}"
    )


def format_payment_admin(payment: MockPayment) -> str:
    """Format payment for admin notification"""
    return (
        f"💳 <b>New Payment Verification Request</b>\n"
        f"{'─' * 30}\n"
        f"👤 <b>Name:</b> {payment.full_name or 'N/A'}\n"
        f"🐦 <b>Username:</b> @{payment.username or 'N/A'}\n"
        f"🆔 <b>User ID:</b> <code>{payment.user_id}</code>\n"
        f"💵 <b>Amount:</b> ₹{payment.amount:.2f}\n"
        f"📱 <b>UPI ID:</b> <code>{payment.upi_id_used}</code>\n"
        f"🔑 <b>UTR Number:</b> <code>{payment.utr_number or 'Not provided'}</code>\n"
        f"⏰ <b>Time:</b> {payment.created_at.strftime('%d %b %Y %H:%M')} UTC"
    )


async def get_revenue_stats() -> dict:
    """Get revenue statistics"""
    async with AsyncSessionLocal() as session:
        # Total approved payments
        result = await session.execute(
            select(func.sum(MockPayment.amount), func.count(MockPayment.id))
            .where(MockPayment.payment_status == "approved")
        )
        total_revenue, total_paid = result.one()
        
        # Pending payments
        result = await session.execute(
            select(func.count(MockPayment.id))
            .where(MockPayment.payment_status == "pending")
        )
        pending_count = result.scalar()
        
        # Today's revenue
        today = datetime.utcnow().date()
        result = await session.execute(
            select(func.sum(MockPayment.amount))
            .where(
                MockPayment.payment_status == "approved",
                func.date(MockPayment.updated_at) == today
            )
        )
        daily_revenue = result.scalar() or 0
        
        # Total registrations
        result = await session.execute(select(func.count(Registration.id)))
        total_registrations = result.scalar()
        
        # Scheduled interviews
        result = await session.execute(
            select(func.count(Registration.id))
            .where(Registration.scheduled_date.isnot(None))
        )
        scheduled = result.scalar()
        
    return {
        "total_revenue": total_revenue or 0,
        "total_paid": total_paid or 0,
        "pending_payments": pending_count or 0,
        "daily_revenue": daily_revenue,
        "total_registrations": total_registrations or 0,
        "scheduled_interviews": scheduled or 0,
    }
