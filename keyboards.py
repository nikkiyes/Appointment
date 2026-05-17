"""
Keyboards module - all inline and reply keyboards
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ─── Main Menu ───────────────────────────────────────────────────────────────

def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📅 Book Your Appointment for Interview",
            callback_data="book_interview"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🎯 Paid Mock Interview",
            callback_data="mock_interview"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔐 Admin Panel",
            callback_data="admin_panel"
        )
    )
    return builder.as_markup()


# ─── Booking Flow ─────────────────────────────────────────────────────────────

def date_range_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📆 1–10 June", callback_data="range_1_10"),
        InlineKeyboardButton(text="📆 11–20 June", callback_data="range_11_20"),
    )
    builder.row(
        InlineKeyboardButton(text="📆 21–30 June", callback_data="range_21_30"),
    )
    builder.row(cancel_button())
    return builder.as_markup()


def confirm_booking_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Confirm & Submit", callback_data="confirm_booking"),
        InlineKeyboardButton(text="✏️ Edit Details", callback_data="edit_booking"),
    )
    builder.row(cancel_button())
    return builder.as_markup()


def edit_booking_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Name", callback_data="edit_name"),
        InlineKeyboardButton(text="🔢 Roll No", callback_data="edit_roll"),
    )
    builder.row(
        InlineKeyboardButton(text="🏫 SIB", callback_data="edit_sib"),
        InlineKeyboardButton(text="📅 Date Range", callback_data="edit_date_range"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Introduction", callback_data="edit_intro"),
        InlineKeyboardButton(text="📆 Preferred Date", callback_data="edit_preferred"),
    )
    builder.row(
        InlineKeyboardButton(text="📎 Screenshot", callback_data="edit_screenshot"),
    )
    builder.row(cancel_button())
    return builder.as_markup()


# ─── Mock Interview ───────────────────────────────────────────────────────────

def mock_interview_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💳 Proceed to Pay", callback_data="mock_pay"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
    )
    return builder.as_markup()


def payment_qr_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ I Have Paid", callback_data="payment_paid"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
    )
    return builder.as_markup()


def payment_proof_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔢 Enter UTR Number", callback_data="proof_utr"),
        InlineKeyboardButton(text="📸 Upload Screenshot", callback_data="proof_screenshot"),
    )
    builder.row(cancel_button())
    return builder.as_markup()


# ─── Admin Payment Approval ───────────────────────────────────────────────────

def admin_payment_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Approve Payment",
            callback_data=f"approve_payment_{payment_id}"
        ),
        InlineKeyboardButton(
            text="❌ Decline Payment",
            callback_data=f"decline_payment_{payment_id}"
        ),
    )
    return builder.as_markup()


# ─── Admin Panel ──────────────────────────────────────────────────────────────

def admin_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Registered Users", callback_data="admin_users"),
        InlineKeyboardButton(text="💰 Mock Interview Users", callback_data="admin_paid"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Revenue Dashboard", callback_data="admin_revenue"),
        InlineKeyboardButton(text="📈 Statistics", callback_data="admin_stats"),
    )
    builder.row(
        InlineKeyboardButton(text="⬇️ Download CSV", callback_data="admin_csv"),
        InlineKeyboardButton(text="📋 Today's Interview List", callback_data="admin_today"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Schedule Interview", callback_data="admin_schedule"),
        InlineKeyboardButton(text="🔗 Send Meet Link", callback_data="admin_meet"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Broadcast Message", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="🔍 Search Student", callback_data="admin_search"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Export Introductions", callback_data="admin_export_intro"),
        InlineKeyboardButton(text="⏳ Pending Payments", callback_data="admin_pending"),
    )
    builder.row(
        InlineKeyboardButton(text="✅ Approved Payments", callback_data="admin_approved"),
        InlineKeyboardButton(text="⚙️ Payment Settings", callback_data="admin_payment_settings"),
    )
    builder.row(
        InlineKeyboardButton(text="⬇️ Download Payment CSV", callback_data="admin_payment_csv"),
        InlineKeyboardButton(text="🚪 Logout", callback_data="admin_logout"),
    )
    return builder.as_markup()


def admin_csv_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 1–10 June", callback_data="csv_1_10"),
        InlineKeyboardButton(text="📅 11–20 June", callback_data="csv_11_20"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 21–30 June", callback_data="csv_21_30"),
        InlineKeyboardButton(text="📅 All Students", callback_data="csv_all"),
    )
    builder.row(back_button("admin_back"))
    return builder.as_markup()


def admin_payment_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💵 Set Price", callback_data="set_price"),
        InlineKeyboardButton(text="📱 Update UPI ID", callback_data="set_upi"),
    )
    builder.row(
        InlineKeyboardButton(text="👤 Update Payee Name", callback_data="set_payee"),
        InlineKeyboardButton(text="🔄 Toggle Payments", callback_data="toggle_payments"),
    )
    builder.row(
        InlineKeyboardButton(text="👁 View Current Settings", callback_data="view_payment_settings"),
    )
    builder.row(back_button("admin_back"))
    return builder.as_markup()


def pagination_keyboard(
    current_page: int, total_pages: int, prefix: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Prev", callback_data=f"{prefix}_page_{current_page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📄 {current_page}/{total_pages}", callback_data="noop"
        )
    )
    if current_page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(text="Next ➡️", callback_data=f"{prefix}_page_{current_page + 1}")
        )
    builder.row(*nav_buttons)
    builder.row(back_button("admin_back"))
    return builder.as_markup()


# ─── Utility ──────────────────────────────────────────────────────────────────

def cancel_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")


def back_button(callback: str = "back") -> InlineKeyboardButton:
    return InlineKeyboardButton(text="🔙 Back", callback_data=callback)


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(cancel_button())
    return builder.as_markup()


def home_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Back to Home", callback_data="home")
    )
    return builder.as_markup()


def join_channel_keyboard(channel_link: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Join Channel", url=channel_link)
    )
    builder.row(
        InlineKeyboardButton(text="✅ I've Joined", callback_data="check_join")
    )
    return builder.as_markup()
