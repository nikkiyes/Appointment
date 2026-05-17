"""
Admin Panel Handler - Full admin feature set
"""

import logging
import io
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, or_

from states import AdminStates
from keyboards import (
    admin_main_keyboard,
    admin_csv_keyboard,
    admin_payment_settings_keyboard,
    pagination_keyboard,
    cancel_keyboard,
    home_keyboard,
    back_button,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from database import AsyncSessionLocal, Registration, MockPayment, AdminSession, AdminAuditLog
from utils import (
    export_registrations_csv,
    export_payments_csv,
    export_today_interviews_csv,
    export_introductions_csv,
    get_revenue_stats,
    get_all_payment_settings,
    set_payment_setting,
    get_payment_setting,
)
from config import settings

router = Router()
logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 5


# ─── Auth ─────────────────────────────────────────────────────────────────────

async def is_admin_logged_in(user_id: int) -> bool:
    # Super admins (from env) always have access
    if user_id in settings.admin_ids_list:
        return True
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AdminSession).where(
                AdminSession.user_id == user_id,
                AdminSession.is_active == True
            )
        )
        return result.scalar_one_or_none() is not None


async def log_admin_action(admin_id: int, admin_username: str, action: str, details: str = None):
    async with AsyncSessionLocal() as session:
        log = AdminAuditLog(
            admin_id=admin_id,
            admin_username=admin_username,
            action=action,
            details=details,
        )
        session.add(log)
        await session.commit()


# ─── Entry Point ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_panel")
async def admin_panel_entry(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if await is_admin_logged_in(user_id):
        await show_admin_menu(callback.message, edit=True)
        await callback.answer()
        return

    await state.set_state(AdminStates.password)
    await callback.message.edit_text(
        "🔐 <b>Admin Panel</b>\n\n"
        "Please enter the admin password to continue:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.password)
async def check_password(message: Message, state: FSMContext):
    if message.text.strip() == settings.ADMIN_PASSWORD:
        user = message.from_user
        # Save session
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AdminSession).where(AdminSession.user_id == user.id)
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.is_active = True
                existing.logged_in_at = datetime.utcnow()
            else:
                session.add(AdminSession(
                    user_id=user.id,
                    username=user.username,
                ))
            await session.commit()

        await log_admin_action(user.id, user.username or "", "LOGIN", "Admin logged in")
        try:
            await message.delete()
        except Exception:
            pass
        await show_admin_menu(message, edit=False)
        await state.clear()
    else:
        await message.answer("❌ <b>Incorrect password.</b> Please try again or /start to cancel:")


async def show_admin_menu(message: Message, edit: bool = False):
    text = "🔐 <b>Admin Panel</b>\n\nWelcome! Select an option:"
    if edit:
        await message.edit_text(text, reply_markup=admin_main_keyboard())
    else:
        await message.answer(text, reply_markup=admin_main_keyboard())


# ─── Logout ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_logout")
async def admin_logout(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AdminSession).where(AdminSession.user_id == user.id)
        )
        session_obj = result.scalar_one_or_none()
        if session_obj:
            session_obj.is_active = False
            await session.commit()

    await log_admin_action(user.id, user.username or "", "LOGOUT", "Admin logged out")
    await state.clear()
    await callback.message.edit_text(
        "👋 <b>Logged out successfully.</b>",
        reply_markup=home_keyboard()
    )
    await callback.answer("Logged out")


# ─── Guard for all admin callbacks ───────────────────────────────────────────

async def guard(callback: CallbackQuery) -> bool:
    if not await is_admin_logged_in(callback.from_user.id):
        await callback.answer("⛔ Access denied. Please login first.", show_alert=True)
        return False
    return True


# ─── 1. View Registered Users ─────────────────────────────────────────────────

@router.callback_query(F.data == "admin_users")
async def view_users(callback: CallbackQuery, state: FSMContext):
    if not await guard(callback):
        return
    await state.update_data(users_page=1, users_filter=None)
    await show_users_page(callback, 1, search=None)
    await callback.answer()


@router.callback_query(F.data.startswith("users_page_"))
async def users_page(callback: CallbackQuery, state: FSMContext):
    if not await guard(callback):
        return
    page = int(callback.data.split("_")[2])
    data = await state.get_data()
    await show_users_page(callback, page, search=data.get("users_filter"))
    await callback.answer()


async def show_users_page(callback: CallbackQuery, page: int, search: str = None):
    async with AsyncSessionLocal() as session:
        query = select(Registration).order_by(Registration.created_at.desc())
        if search:
            query = query.where(
                or_(
                    Registration.full_name.ilike(f"%{search}%"),
                    Registration.roll_number.ilike(f"%{search}%"),
                    Registration.sib.ilike(f"%{search}%"),
                    Registration.serial_number.ilike(f"%{search}%"),
                )
            )
        count_result = await session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        page = min(page, total_pages)

        result = await session.execute(
            query.offset((page - 1) * ITEMS_PER_PAGE).limit(ITEMS_PER_PAGE)
        )
        users = result.scalars().all()

    if not users:
        text = "👥 <b>Registered Users</b>\n\n❌ No users found."
    else:
        text = f"👥 <b>Registered Users</b> (Page {page}/{total_pages})\n"
        if search:
            text += f"🔍 Search: <i>{search}</i>\n"
        text += f"Total: <b>{total}</b>\n{'─' * 30}\n"
        for u in users:
            text += (
                f"\n🔖 <code>{u.serial_number}</code> | {u.full_name}\n"
                f"   📋 Roll: {u.roll_number} | SIB: {u.sib}\n"
                f"   📅 Range: {u.date_range}\n"
                f"   🐦 @{u.username or 'N/A'} | 🕐 {u.created_at.strftime('%d %b %Y')}\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=pagination_keyboard(page, total_pages, "users")
    )


# ─── 2. Paid Mock Interview Users ─────────────────────────────────────────────

@router.callback_query(F.data == "admin_paid")
async def view_paid_users(callback: CallbackQuery):
    if not await guard(callback):
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MockPayment)
            .where(MockPayment.payment_status == "approved")
            .order_by(MockPayment.updated_at.desc())
        )
        payments = result.scalars().all()

    if not payments:
        text = "💰 <b>Paid Mock Interview Users</b>\n\n❌ No approved payments."
    else:
        text = f"💰 <b>Paid Mock Interview Users</b>\nTotal: <b>{len(payments)}</b>\n{'─' * 30}\n"
        for p in payments[:20]:
            text += (
                f"\n👤 {p.full_name or 'N/A'} | @{p.username or 'N/A'}\n"
                f"   💵 ₹{p.amount:.2f} | UTR: <code>{p.utr_number or 'N/A'}</code>\n"
                f"   ✅ Approved by: {p.approved_by_name or 'N/A'}\n"
                f"   🕐 {p.created_at.strftime('%d %b %Y %H:%M')}\n"
            )

    builder = InlineKeyboardBuilder()
    builder.row(back_button("admin_back"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ─── 3. Revenue Dashboard ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_revenue")
async def revenue_dashboard(callback: CallbackQuery):
    if not await guard(callback):
        return

    stats = await get_revenue_stats()
    text = (
        f"📊 <b>Revenue Dashboard</b>\n\n"
        f"💰 <b>Total Revenue:</b> ₹{stats['total_revenue']:.2f}\n"
        f"👥 <b>Total Paid Users:</b> {stats['total_paid']}\n"
        f"⏳ <b>Pending Payments:</b> {stats['pending_payments']}\n"
        f"📅 <b>Today's Revenue:</b> ₹{stats['daily_revenue']:.2f}\n\n"
        f"📋 <b>Overall Stats:</b>\n"
        f"📝 Total Registrations: {stats['total_registrations']}\n"
        f"📅 Scheduled Interviews: {stats['scheduled_interviews']}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(back_button("admin_back"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ─── 4. Download CSV ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_csv")
async def download_csv_menu(callback: CallbackQuery):
    if not await guard(callback):
        return
    await callback.message.edit_text(
        "⬇️ <b>Download CSV</b>\n\nSelect date range:",
        reply_markup=admin_csv_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("csv_"))
async def send_csv(callback: CallbackQuery):
    if not await guard(callback):
        return

    range_map = {
        "csv_1_10": "1–10 June",
        "csv_11_20": "11–20 June",
        "csv_21_30": "21–30 June",
        "csv_all": None,
    }

    date_filter = range_map.get(callback.data)
    filename = f"students_{callback.data.replace('csv_', '')}_{datetime.utcnow().strftime('%Y%m%d')}.csv"

    await callback.answer("⏳ Generating CSV...")
    csv_bytes = await export_registrations_csv(date_filter)

    await callback.message.answer_document(
        BufferedInputFile(csv_bytes, filename=filename),
        caption=f"📊 Student list export\n🕐 {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC"
    )
    await log_admin_action(
        callback.from_user.id, callback.from_user.username or "",
        "EXPORT_CSV", f"Downloaded CSV: {filename}"
    )


# ─── 5. Schedule Interview ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_schedule")
async def schedule_interview_start(callback: CallbackQuery, state: FSMContext):
    if not await guard(callback):
        return
    await state.set_state(AdminStates.select_student)
    await callback.message.edit_text(
        "📅 <b>Schedule Interview</b>\n\n"
        "Enter the student's <b>Roll Number</b> or <b>Serial Number</b> to schedule:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.select_student)
async def select_student_for_schedule(message: Message, state: FSMContext):
    query = message.text.strip()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Registration).where(
                or_(
                    Registration.roll_number == query,
                    Registration.serial_number == query,
                )
            )
        )
        student = result.scalar_one_or_none()

    if not student:
        await message.answer("❌ Student not found. Try again:")
        return

    await state.update_data(schedule_student_id=student.id, schedule_user_id=student.user_id)
    await state.set_state(AdminStates.set_date)
    await message.answer(
        f"✅ Student found: <b>{student.full_name}</b> ({student.serial_number})\n\n"
        "Enter the <b>interview date</b> (e.g., 15 June 2024):",
        reply_markup=cancel_keyboard()
    )


@router.message(AdminStates.set_date)
async def set_schedule_date(message: Message, state: FSMContext):
    await state.update_data(schedule_date=message.text.strip())
    await state.set_state(AdminStates.set_time)
    await message.answer(
        "Enter the <b>interview time</b> (e.g., 10:30 AM):",
        reply_markup=cancel_keyboard()
    )


@router.message(AdminStates.set_time)
async def set_schedule_time(message: Message, state: FSMContext):
    data = await state.get_data()
    time_str = message.text.strip()
    today_date = data.get("schedule_date")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Registration).where(Registration.id == data["schedule_student_id"])
        )
        student = result.scalar_one_or_none()
        if student:
            student.scheduled_date = today_date
            student.scheduled_time = time_str
            await session.commit()

    # Notify student
    try:
        await message.bot.send_message(
            data["schedule_user_id"],
            f"📅 <b>Interview Scheduled!</b>\n\n"
            f"Your interview has been scheduled.\n\n"
            f"📅 <b>Date:</b> {today_date}\n"
            f"⏰ <b>Time:</b> {time_str}\n\n"
            f"Please be ready 5 minutes before your scheduled time."
        )
    except Exception as e:
        logger.warning(f"Could not notify student: {e}")

    await log_admin_action(
        message.from_user.id, message.from_user.username or "",
        "SCHEDULE_INTERVIEW",
        f"Scheduled for {student.full_name if student else 'N/A'}: {today_date} {time_str}"
    )
    await message.answer(
        f"✅ <b>Interview scheduled!</b>\n\n"
        f"Student: <b>{student.full_name if student else 'N/A'}</b>\n"
        f"Date: {today_date} at {time_str}\n\n"
        f"Student has been notified.",
        reply_markup=admin_main_keyboard()
    )
    await state.clear()


# ─── 6. Send Meet Link ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_meet")
async def send_meet_start(callback: CallbackQuery, state: FSMContext):
    if not await guard(callback):
        return
    await state.set_state(AdminStates.select_student_meet)
    await callback.message.edit_text(
        "🔗 <b>Send Google Meet Link</b>\n\n"
        "Enter student's Roll Number or Serial Number:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.select_student_meet)
async def select_student_meet(message: Message, state: FSMContext):
    query = message.text.strip()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Registration).where(
                or_(
                    Registration.roll_number == query,
                    Registration.serial_number == query,
                )
            )
        )
        student = result.scalar_one_or_none()

    if not student:
        await message.answer("❌ Student not found. Try again:")
        return

    await state.update_data(meet_student_id=student.id, meet_user_id=student.user_id)
    await state.set_state(AdminStates.enter_meet_link)
    await message.answer(
        f"✅ Student: <b>{student.full_name}</b>\n\n"
        "Enter the Google Meet link:",
        reply_markup=cancel_keyboard()
    )


@router.message(AdminStates.enter_meet_link)
async def send_meet_link(message: Message, state: FSMContext):
    data = await state.get_data()
    meet_link = message.text.strip()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Registration).where(Registration.id == data["meet_student_id"])
        )
        student = result.scalar_one_or_none()
        if student:
            student.meet_link = meet_link
            await session.commit()

    try:
        await message.bot.send_message(
            data["meet_user_id"],
            f"🔗 <b>Google Meet Link for Your Interview</b>\n\n"
            f"Your interview meeting link:\n{meet_link}\n\n"
            f"Please join on time. Good luck! 🌟"
        )
    except Exception as e:
        logger.warning(f"Could not send meet link: {e}")

    await log_admin_action(
        message.from_user.id, message.from_user.username or "",
        "SEND_MEET_LINK", f"Sent to {student.full_name if student else 'N/A'}"
    )
    await message.answer("✅ Meet link sent to student!", reply_markup=admin_main_keyboard())
    await state.clear()


# ─── 7. Broadcast Message ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not await guard(callback):
        return
    await state.set_state(AdminStates.broadcast_message)
    await callback.message.edit_text(
        "📢 <b>Broadcast Message</b>\n\n"
        "Enter the message to send to ALL registered users:\n\n"
        "⚠️ <i>This will send to everyone. Use wisely.</i>",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.broadcast_message)
async def send_broadcast(message: Message, state: FSMContext):
    broadcast_text = message.text.strip()
    admin = message.from_user

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Registration.user_id).distinct())
        user_ids = result.scalars().all()

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(
                uid,
                f"📢 <b>Announcement</b>\n\n{broadcast_text}"
            )
            sent += 1
        except Exception:
            failed += 1

    await log_admin_action(
        admin.id, admin.username or "", "BROADCAST",
        f"Sent to {sent} users, {failed} failed"
    )
    await message.answer(
        f"📢 <b>Broadcast Complete!</b>\n\n"
        f"✅ Sent: {sent}\n❌ Failed: {failed}",
        reply_markup=admin_main_keyboard()
    )
    await state.clear()


# ─── 8. Search Student ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_search")
async def search_student_start(callback: CallbackQuery, state: FSMContext):
    if not await guard(callback):
        return
    await state.set_state(AdminStates.search_query)
    await callback.message.edit_text(
        "🔍 <b>Search Student</b>\n\n"
        "Enter name, roll number, SIB, or serial number:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.search_query)
async def do_search(message: Message, state: FSMContext):
    query = message.text.strip()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Registration).where(
                or_(
                    Registration.full_name.ilike(f"%{query}%"),
                    Registration.roll_number.ilike(f"%{query}%"),
                    Registration.sib.ilike(f"%{query}%"),
                    Registration.serial_number.ilike(f"%{query}%"),
                    Registration.username.ilike(f"%{query}%"),
                )
            ).limit(10)
        )
        students = result.scalars().all()

    if not students:
        await message.answer(
            f"🔍 No students found for: <i>{query}</i>",
            reply_markup=admin_main_keyboard()
        )
    else:
        text = f"🔍 <b>Search Results for:</b> <i>{query}</i>\n{'─' * 30}\n"
        for s in students:
            text += (
                f"\n🔖 <code>{s.serial_number}</code>\n"
                f"👤 {s.full_name}\n"
                f"📋 Roll: {s.roll_number} | SIB: {s.sib}\n"
                f"📅 Range: {s.date_range} | Preferred: {s.preferred_date}\n"
                f"🐦 @{s.username or 'N/A'} | 🆔 {s.user_id}\n"
                f"📅 Scheduled: {s.scheduled_date or 'Not yet'} {s.scheduled_time or ''}\n"
                f"🔗 Meet: {s.meet_link or 'Not provided'}\n"
            )

        await message.answer(text, reply_markup=admin_main_keyboard())
    await state.clear()


# ─── 9. Export Introductions ──────────────────────────────────────────────────

@router.callback_query(F.data == "admin_export_intro")
async def export_introductions(callback: CallbackQuery):
    if not await guard(callback):
        return
    await callback.answer("⏳ Generating...")
    csv_bytes = await export_introductions_csv()
    filename = f"introductions_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    await callback.message.answer_document(
        BufferedInputFile(csv_bytes, filename=filename),
        caption="📝 Student introductions export"
    )
    await log_admin_action(
        callback.from_user.id, callback.from_user.username or "",
        "EXPORT_INTRODUCTIONS", "Exported all introductions"
    )


# ─── 10. Pending Payments ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_pending")
async def view_pending_payments(callback: CallbackQuery):
    if not await guard(callback):
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MockPayment)
            .where(MockPayment.payment_status == "pending")
            .order_by(MockPayment.created_at)
        )
        payments = result.scalars().all()

    if not payments:
        text = "⏳ <b>Pending Payments</b>\n\n✅ No pending payments!"
    else:
        text = f"⏳ <b>Pending Payments</b>\nTotal: <b>{len(payments)}</b>\n{'─' * 30}\n"
        for p in payments:
            text += (
                f"\n🆔 #{p.id} | {p.full_name or 'N/A'}\n"
                f"   💵 ₹{p.amount:.2f} | @{p.username or 'N/A'}\n"
                f"   🔑 UTR: {p.utr_number or 'Screenshot'}\n"
                f"   🕐 {p.created_at.strftime('%d %b %H:%M')}\n"
            )

    builder = InlineKeyboardBuilder()
    builder.row(back_button("admin_back"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ─── 11. Approved Payments ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_approved")
async def view_approved_payments(callback: CallbackQuery):
    if not await guard(callback):
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MockPayment)
            .where(MockPayment.payment_status == "approved")
            .order_by(MockPayment.updated_at.desc())
            .limit(20)
        )
        payments = result.scalars().all()

    if not payments:
        text = "✅ <b>Approved Payments</b>\n\n❌ No approved payments yet."
    else:
        text = f"✅ <b>Approved Payments</b> (last 20)\n{'─' * 30}\n"
        for p in payments:
            text += (
                f"\n✅ #{p.id} | {p.full_name or 'N/A'}\n"
                f"   💵 ₹{p.amount:.2f} | @{p.username or 'N/A'}\n"
                f"   👤 By: {p.approved_by_name or 'N/A'}\n"
            )

    builder = InlineKeyboardBuilder()
    builder.row(back_button("admin_back"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ─── 12. Statistics Dashboard ─────────────────────────────────────────────────

@router.callback_query(F.data == "admin_stats")
async def statistics_dashboard(callback: CallbackQuery):
    if not await guard(callback):
        return

    stats = await get_revenue_stats()

    async with AsyncSessionLocal() as session:
        # By date range
        date_ranges = {
            "range_1_10": "1–10 June",
            "range_11_20": "11–20 June",
            "range_21_30": "21–30 June",
        }
        for key, dr in date_ranges.items():
            result = await session.execute(
                select(func.count(Registration.id))
                .where(Registration.date_range == dr)
            )
            stats[key] = result.scalar() or 0

        # Declined payments
        result = await session.execute(
            select(func.count(MockPayment.id))
            .where(MockPayment.payment_status == "declined")
        )
        stats["declined"] = result.scalar() or 0

    text = (
        f"📈 <b>Statistics Dashboard</b>\n\n"
        f"<b>📋 Registrations:</b>\n"
        f"• Total: {stats['total_registrations']}\n"
        f"• Scheduled: {stats['scheduled_interviews']}\n"
        f"• 1–10 June: {stats['range_1_10']}\n"
        f"• 11–20 June: {stats['range_11_20']}\n"
        f"• 21–30 June: {stats['range_21_30']}\n\n"
        f"<b>💳 Payments:</b>\n"
        f"• Paid Users: {stats['total_paid']}\n"
        f"• Pending: {stats['pending_payments']}\n"
        f"• Declined: {stats['declined']}\n\n"
        f"<b>💰 Revenue:</b>\n"
        f"• Total: ₹{stats['total_revenue']:.2f}\n"
        f"• Today: ₹{stats['daily_revenue']:.2f}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(back_button("admin_back"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ─── 13. Payment Settings ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_payment_settings")
async def payment_settings_menu(callback: CallbackQuery):
    if not await guard(callback):
        return
    await callback.message.edit_text(
        "⚙️ <b>Payment Settings</b>\n\nSelect what to update:",
        reply_markup=admin_payment_settings_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "view_payment_settings")
async def view_payment_settings(callback: CallbackQuery):
    if not await guard(callback):
        return
    s = await get_all_payment_settings()
    text = (
        f"⚙️ <b>Current Payment Settings</b>\n\n"
        f"💵 Price: ₹{s.get('mock_price', 'N/A')}\n"
        f"📱 UPI ID: <code>{s.get('upi_id', 'N/A')}</code>\n"
        f"👤 Payee: {s.get('payee_name', 'N/A')}\n"
        f"🔄 Payments: {'✅ Enabled' if s.get('payments_enabled') == 'true' else '❌ Disabled'}"
    )
    builder = InlineKeyboardBuilder()
    builder.row(back_button("admin_payment_settings"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "toggle_payments")
async def toggle_payments(callback: CallbackQuery):
    if not await guard(callback):
        return
    current = await get_payment_setting("payments_enabled")
    new_val = "false" if current == "true" else "true"
    await set_payment_setting("payments_enabled", new_val)
    status = "✅ Enabled" if new_val == "true" else "❌ Disabled"
    await callback.answer(f"Payments {status}!", show_alert=True)
    await log_admin_action(
        callback.from_user.id, callback.from_user.username or "",
        "TOGGLE_PAYMENTS", f"Payments set to {new_val}"
    )
    await payment_settings_menu(callback)


@router.callback_query(F.data == "set_price")
async def set_price_start(callback: CallbackQuery, state: FSMContext):
    if not await guard(callback):
        return
    await state.set_state(AdminStates.set_price)
    await callback.message.edit_text(
        "💵 Enter new mock interview price (e.g., 99):",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.set_price)
async def save_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip())
        await set_payment_setting("mock_price", str(price))
        await log_admin_action(
            message.from_user.id, message.from_user.username or "",
            "SET_PRICE", f"Price set to ₹{price}"
        )
        await message.answer(
            f"✅ Price updated to ₹{price:.2f}",
            reply_markup=admin_main_keyboard()
        )
    except ValueError:
        await message.answer("❌ Invalid price. Enter a number:")
        return
    await state.clear()


@router.callback_query(F.data == "set_upi")
async def set_upi_start(callback: CallbackQuery, state: FSMContext):
    if not await guard(callback):
        return
    await state.set_state(AdminStates.set_upi)
    await callback.message.edit_text(
        "📱 Enter new UPI ID (e.g., name@upi):",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.set_upi)
async def save_upi(message: Message, state: FSMContext):
    upi = message.text.strip()
    await set_payment_setting("upi_id", upi)
    await log_admin_action(
        message.from_user.id, message.from_user.username or "",
        "SET_UPI", f"UPI ID set to {upi}"
    )
    await message.answer(f"✅ UPI ID updated to <code>{upi}</code>", reply_markup=admin_main_keyboard())
    await state.clear()


@router.callback_query(F.data == "set_payee")
async def set_payee_start(callback: CallbackQuery, state: FSMContext):
    if not await guard(callback):
        return
    await state.set_state(AdminStates.set_payee)
    await callback.message.edit_text(
        "👤 Enter new payee name:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.set_payee)
async def save_payee(message: Message, state: FSMContext):
    name = message.text.strip()
    await set_payment_setting("payee_name", name)
    await log_admin_action(
        message.from_user.id, message.from_user.username or "",
        "SET_PAYEE", f"Payee set to {name}"
    )
    await message.answer(f"✅ Payee name updated to <b>{name}</b>", reply_markup=admin_main_keyboard())
    await state.clear()


# ─── 14. Today's Interview List ───────────────────────────────────────────────

@router.callback_query(F.data == "admin_today")
async def download_today_list(callback: CallbackQuery):
    if not await guard(callback):
        return
    await callback.answer("⏳ Generating...")
    csv_bytes = await export_today_interviews_csv()
    filename = f"today_interviews_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    await callback.message.answer_document(
        BufferedInputFile(csv_bytes, filename=filename),
        caption=f"📅 Today's interview list\n🕐 {datetime.utcnow().strftime('%d %b %Y')}"
    )
    await log_admin_action(
        callback.from_user.id, callback.from_user.username or "",
        "EXPORT_TODAY_LIST", "Exported today's interview list"
    )


# ─── Payment CSV Download ─────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_payment_csv")
async def download_payment_csv(callback: CallbackQuery):
    if not await guard(callback):
        return
    await callback.answer("⏳ Generating...")
    csv_bytes = await export_payments_csv()
    filename = f"payments_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    await callback.message.answer_document(
        BufferedInputFile(csv_bytes, filename=filename),
        caption="💳 All payment records export"
    )
    await log_admin_action(
        callback.from_user.id, callback.from_user.username or "",
        "EXPORT_PAYMENTS_CSV", "Exported payment CSV"
    )
