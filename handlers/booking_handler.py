"""
Booking handler - Step-by-step interview registration flow
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import BookingStates
from keyboards import (
    date_range_keyboard,
    confirm_booking_keyboard,
    edit_booking_keyboard,
    cancel_keyboard,
    home_keyboard,
)
from database import AsyncSessionLocal, Registration
from utils import (
    generate_serial_number,
    format_registration_summary,
    format_admin_registration,
)
from config import settings
from sqlalchemy import select

router = Router()
logger = logging.getLogger(__name__)

DATE_RANGE_MAP = {
    "range_1_10": "1–10 June",
    "range_11_20": "11–20 June",
    "range_21_30": "21–30 June",
}


# ─── Step 1: Start Booking ────────────────────────────────────────────────────

@router.callback_query(F.data == "book_interview")
async def start_booking(callback: CallbackQuery, state: FSMContext):
    """Begin booking flow"""
    user_id = callback.from_user.id

    # Check duplicate registration
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Registration).where(Registration.user_id == user_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            await callback.message.edit_text(
                f"⚠️ <b>Already Registered!</b>\n\n"
                f"You have already submitted a registration.\n"
                f"🔖 <b>Serial Number:</b> <code>{existing.serial_number}</code>\n\n"
                f"Contact admin if you need to make changes.",
                reply_markup=home_keyboard()
            )
            await callback.answer()
            return

    await state.set_state(BookingStates.full_name)
    await callback.message.edit_text(
        "📅 <b>Book Your Interview Appointment</b>\n\n"
        "Let's get your details. You can cancel anytime.\n\n"
        "<b>Step 1/7</b> — Please enter your <b>Full Name</b>:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


# ─── Step 2: Roll Number ──────────────────────────────────────────────────────

@router.message(BookingStates.full_name)
async def get_full_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Name too short. Please enter your full name:")
        return
    await state.update_data(full_name=name)
    await state.set_state(BookingStates.roll_number)
    await message.answer(
        f"✅ <b>Name:</b> {name}\n\n"
        "<b>Step 2/7</b> — Enter your <b>Roll Number</b>:",
        reply_markup=cancel_keyboard()
    )


# ─── Step 3: SIB ─────────────────────────────────────────────────────────────

@router.message(BookingStates.roll_number)
async def get_roll_number(message: Message, state: FSMContext):
    roll = message.text.strip()
    if not roll:
        await message.answer("❌ Please enter a valid roll number:")
        return

    # Check duplicate roll number
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Registration).where(Registration.roll_number == roll)
        )
        if result.scalar_one_or_none():
            await message.answer(
                "❌ <b>Duplicate Roll Number!</b>\n\n"
                "This roll number is already registered. "
                "Please contact admin if this is an error.",
                reply_markup=home_keyboard()
            )
            await state.clear()
            return

    await state.update_data(roll_number=roll)
    await state.set_state(BookingStates.sib)
    await message.answer(
        f"✅ <b>Roll Number:</b> {roll}\n\n"
        "<b>Step 3/7</b> — Enter your <b>SIB</b>:",
        reply_markup=cancel_keyboard()
    )


# ─── Step 4: Date Range ───────────────────────────────────────────────────────

@router.message(BookingStates.sib)
async def get_sib(message: Message, state: FSMContext):
    sib = message.text.strip()
    if not sib:
        await message.answer("❌ Please enter a valid SIB:")
        return
    await state.update_data(sib=sib)
    await state.set_state(BookingStates.date_range)
    await message.answer(
        f"✅ <b>SIB:</b> {sib}\n\n"
        "<b>Step 4/7</b> — Select your <b>Interview Date Range</b>:",
        reply_markup=date_range_keyboard()
    )


@router.callback_query(F.data.startswith("range_"))
async def get_date_range(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state != BookingStates.date_range:
        await callback.answer()
        return

    date_range = DATE_RANGE_MAP.get(callback.data, "Unknown")
    await state.update_data(date_range=date_range)
    await state.set_state(BookingStates.introduction)
    await callback.message.edit_text(
        f"✅ <b>Date Range:</b> {date_range}\n\n"
        "<b>Step 5/7</b> — Write your <b>Full Introduction</b>:\n\n"
        "💡 <i>Be detailed — include your background, experience, and skills. "
        "Long text is fully supported.</i>",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


# ─── Step 5: Introduction ────────────────────────────────────────────────────

@router.message(BookingStates.introduction)
async def get_introduction(message: Message, state: FSMContext):
    intro = message.text.strip()
    if len(intro) < 20:
        await message.answer(
            "❌ Introduction is too short. Please write a proper introduction (at least 20 characters):"
        )
        return
    await state.update_data(introduction=intro)
    await state.set_state(BookingStates.preferred_date)
    await message.answer(
        "✅ <b>Introduction saved!</b>\n\n"
        "<b>Step 6/7</b> — Enter your <b>Preferred Interview Date</b>:\n\n"
        "ℹ️ <i>We will try to schedule your interview on your preferred date, "
        "but it is not guaranteed.</i>",
        reply_markup=cancel_keyboard()
    )


# ─── Step 6: Preferred Date ───────────────────────────────────────────────────

@router.message(BookingStates.preferred_date)
async def get_preferred_date(message: Message, state: FSMContext):
    date = message.text.strip()
    if not date:
        await message.answer("❌ Please enter your preferred date:")
        return
    await state.update_data(preferred_date=date)
    await state.set_state(BookingStates.screenshot)
    await message.answer(
        f"✅ <b>Preferred Date:</b> {date}\n\n"
        "<b>Step 7/7</b> — Please upload a <b>Screenshot/PDF/Image</b> of your "
        "official interview email or appointment confirmation:",
        reply_markup=cancel_keyboard()
    )


# ─── Step 7: Screenshot ──────────────────────────────────────────────────────

@router.message(BookingStates.screenshot, F.photo)
async def get_screenshot_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(
        screenshot_file_id=photo.file_id,
        screenshot_file_type="photo"
    )
    await show_confirmation(message, state)


@router.message(BookingStates.screenshot, F.document)
async def get_screenshot_document(message: Message, state: FSMContext):
    doc = message.document
    await state.update_data(
        screenshot_file_id=doc.file_id,
        screenshot_file_type="document"
    )
    await show_confirmation(message, state)


@router.message(BookingStates.screenshot)
async def screenshot_invalid(message: Message, state: FSMContext):
    await message.answer(
        "❌ Please upload a <b>photo</b>, <b>image</b>, or <b>PDF document</b>:"
    )


# ─── Confirmation ─────────────────────────────────────────────────────────────

async def show_confirmation(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(BookingStates.confirm)
    summary = format_registration_summary(data)
    await message.answer(
        f"✅ <b>Screenshot uploaded!</b>\n\n"
        f"<b>Please review your details:</b>\n\n"
        f"{summary}\n\n"
        f"👆 Do you want to <b>confirm</b> your registration or <b>edit</b> any details?",
        reply_markup=confirm_booking_keyboard()
    )


@router.callback_query(F.data == "confirm_booking", BookingStates.confirm)
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    """Final submission"""
    data = await state.get_data()
    user = callback.from_user

    await callback.message.edit_text("⏳ <b>Submitting your registration...</b>")

    try:
        serial = await generate_serial_number()

        reg = Registration(
            serial_number=serial,
            user_id=user.id,
            username=user.username,
            full_name=data["full_name"],
            roll_number=data["roll_number"],
            sib=data["sib"],
            date_range=data["date_range"],
            introduction=data["introduction"],
            preferred_date=data["preferred_date"],
            screenshot_file_id=data.get("screenshot_file_id"),
            screenshot_file_type=data.get("screenshot_file_type"),
            interview_type="real",
        )

        async with AsyncSessionLocal() as session:
            session.add(reg)
            await session.commit()
            await session.refresh(reg)

        # Confirmation to user
        await callback.message.edit_text(
            f"🎉 <b>Registration Successful!</b>\n\n"
            f"Thank you for registering.\n"
            f"Your details have been submitted successfully.\n"
            f"We will inform you shortly about your interview date and timing.\n\n"
            f"🔖 <b>Your Serial Number:</b> <code>{serial}</code>\n\n"
            f"<i>Please save this serial number for your reference.</i>",
            reply_markup=home_keyboard()
        )

        # Notify admin group
        await notify_admin_registration(callback.bot, reg)
        await state.clear()

    except Exception as e:
        logger.error(f"Registration error: {e}")
        await callback.message.edit_text(
            "❌ <b>Registration failed.</b>\n\nPlease try again or contact admin.",
            reply_markup=home_keyboard()
        )

    await callback.answer()


async def notify_admin_registration(bot, reg: Registration):
    """Send registration details to admin group"""
    if not settings.ADMIN_GROUP_ID:
        return

    try:
        admin_msg = format_admin_registration(reg)

        if reg.screenshot_file_id:
            if reg.screenshot_file_type == "photo":
                await bot.send_photo(
                    settings.ADMIN_GROUP_ID,
                    photo=reg.screenshot_file_id,
                    caption=admin_msg,
                )
            else:
                await bot.send_document(
                    settings.ADMIN_GROUP_ID,
                    document=reg.screenshot_file_id,
                    caption=admin_msg,
                )
        else:
            await bot.send_message(settings.ADMIN_GROUP_ID, admin_msg)

    except Exception as e:
        logger.error(f"Failed to notify admin group: {e}")


# ─── Edit Flow ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "edit_booking")
async def edit_booking(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ <b>Edit Your Details</b>\n\nWhich field would you like to edit?",
        reply_markup=edit_booking_keyboard()
    )
    await callback.answer()


EDIT_PROMPTS = {
    "edit_name": ("full_name", BookingStates.full_name, "Enter your new <b>Full Name</b>:"),
    "edit_roll": ("roll_number", BookingStates.roll_number, "Enter your new <b>Roll Number</b>:"),
    "edit_sib": ("sib", BookingStates.sib, "Enter your new <b>SIB</b>:"),
    "edit_date_range": ("date_range", BookingStates.date_range, "Select your <b>Date Range</b>:"),
    "edit_intro": ("introduction", BookingStates.introduction, "Enter your new <b>Introduction</b>:"),
    "edit_preferred": ("preferred_date", BookingStates.preferred_date, "Enter your new <b>Preferred Date</b>:"),
    "edit_screenshot": ("screenshot_file_id", BookingStates.screenshot, "Upload your new <b>Screenshot/PDF</b>:"),
}


@router.callback_query(F.data.startswith("edit_"))
async def handle_edit(callback: CallbackQuery, state: FSMContext):
    edit_key = callback.data
    if edit_key not in EDIT_PROMPTS:
        await callback.answer()
        return

    field, new_state, prompt = EDIT_PROMPTS[edit_key]
    await state.set_state(new_state)

    if new_state == BookingStates.date_range:
        await callback.message.edit_text(
            f"✏️ {prompt}", reply_markup=date_range_keyboard()
        )
    else:
        await callback.message.edit_text(
            f"✏️ {prompt}", reply_markup=cancel_keyboard()
        )
    await callback.answer()
