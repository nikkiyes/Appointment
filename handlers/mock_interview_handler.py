"""
Mock Interview and Payment handler
"""

import logging
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from states import MockInterviewStates
from keyboards import (
    mock_interview_keyboard,
    payment_qr_keyboard,
    payment_proof_keyboard,
    admin_payment_keyboard,
    home_keyboard,
    cancel_keyboard,
)
from database import AsyncSessionLocal, MockPayment
from utils import (
    get_payment_setting,
    generate_upi_qr,
    format_payment_admin,
)
from config import settings
from sqlalchemy import select

router = Router()
logger = logging.getLogger(__name__)

MOCK_INFO_TEXT = (
    "🎯 <b>Mock Interview Session</b>\n\n"
    "📋 <b>Details:</b>\n"
    "• Duration: <b>10–20 minutes</b>\n"
    "• Proper interview evaluation\n"
    "• Conducted today or next day\n\n"
    "📌 <b>Requirements:</b>\n"
    "• Sit in proper lighting\n"
    "• Use good camera and audio\n"
    "• Formal behavior recommended\n\n"
    "Would you like to proceed with payment?"
)


# ─── Show Mock Interview Info ─────────────────────────────────────────────────

@router.callback_query(F.data == "mock_interview")
async def show_mock_info(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MockInterviewStates.confirm_info)
    await callback.message.edit_text(
        MOCK_INFO_TEXT,
        reply_markup=mock_interview_keyboard()
    )
    await callback.answer()


# ─── Proceed to Payment ───────────────────────────────────────────────────────

@router.callback_query(F.data == "mock_pay", MockInterviewStates.confirm_info)
async def proceed_to_pay(callback: CallbackQuery, state: FSMContext):
    # Check if payments are enabled
    payments_enabled = await get_payment_setting("payments_enabled")
    if payments_enabled != "true":
        await callback.answer(
            "⚠️ Payments are currently disabled. Please contact admin.",
            show_alert=True
        )
        return

    # Fetch payment settings
    price = float(await get_payment_setting("mock_price") or settings.DEFAULT_MOCK_PRICE)
    upi_id = await get_payment_setting("upi_id") or settings.DEFAULT_UPI_ID
    payee_name = await get_payment_setting("payee_name") or settings.DEFAULT_PAYEE_NAME

    # Generate QR code
    qr_bytes, upi_link = generate_upi_qr(upi_id, payee_name, price)

    # Store payment session data
    expiry = datetime.utcnow() + timedelta(minutes=settings.PAYMENT_EXPIRY_MINUTES)
    await state.update_data(
        price=price,
        upi_id=upi_id,
        payee_name=payee_name,
        upi_link=upi_link,
        payment_expiry=expiry.isoformat()
    )
    await state.set_state(MockInterviewStates.payment_pending)

    payment_text = (
        f"💳 <b>Payment Details</b>\n\n"
        f"💵 <b>Amount:</b> ₹{price:.2f}\n"
        f"📱 <b>UPI ID:</b> <code>{upi_id}</code>\n"
        f"👤 <b>Payee:</b> {payee_name}\n\n"
        f"<b>Instructions:</b>\n"
        f"1. Open any UPI app (GPay, PhonePe, Paytm)\n"
        f"2. Scan the QR code below OR pay to UPI ID\n"
        f"3. Pay exactly <b>₹{price:.2f}</b>\n"
        f"4. Click <b>'I Have Paid'</b> after payment\n\n"
        f"⏳ <b>Payment expires in {settings.PAYMENT_EXPIRY_MINUTES} minutes</b>"
    )

    qr_input = BufferedInputFile(qr_bytes, filename="payment_qr.png")
    await callback.message.answer_photo(
        photo=qr_input,
        caption=payment_text,
        reply_markup=payment_qr_keyboard()
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


# ─── Payment Paid ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "payment_paid", MockInterviewStates.payment_pending)
async def payment_paid(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    # Check expiry
    expiry = datetime.fromisoformat(data.get("payment_expiry", datetime.utcnow().isoformat()))
    if datetime.utcnow() > expiry:
        await callback.answer(
            "⏰ Payment session expired. Please start again.",
            show_alert=True
        )
        await state.clear()
        await callback.message.edit_caption(
            "⏰ <b>Payment expired.</b>",
            reply_markup=home_keyboard()
        )
        return

    await state.set_state(MockInterviewStates.payment_proof)
    await callback.message.answer(
        "✅ <b>Payment Submitted!</b>\n\n"
        "Now please provide your payment proof:\n\n"
        "Choose one of the options below:",
        reply_markup=payment_proof_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "proof_utr", MockInterviewStates.payment_proof)
async def ask_utr(callback: CallbackQuery, state: FSMContext):
    await state.update_data(proof_type="utr")
    await state.set_state(MockInterviewStates.utr_or_screenshot)
    await callback.message.edit_text(
        "🔢 <b>Enter UTR Number</b>\n\n"
        "Please enter the 12-digit UTR number from your payment confirmation:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "proof_screenshot", MockInterviewStates.payment_proof)
async def ask_screenshot(callback: CallbackQuery, state: FSMContext):
    await state.update_data(proof_type="screenshot")
    await state.set_state(MockInterviewStates.utr_or_screenshot)
    await callback.message.edit_text(
        "📸 <b>Upload Payment Screenshot</b>\n\n"
        "Please upload a screenshot of your payment confirmation:",
        reply_markup=cancel_keyboard()
    )
    await callback.answer()


# ─── Receive UTR ──────────────────────────────────────────────────────────────

@router.message(MockInterviewStates.utr_or_screenshot, F.text)
async def receive_utr(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("proof_type") != "utr":
        await message.answer("❌ Please upload a screenshot image:")
        return

    utr = message.text.strip()
    if len(utr) < 6:
        await message.answer("❌ Invalid UTR. Please enter the correct UTR number:")
        return

    # Check duplicate UTR
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MockPayment).where(MockPayment.utr_number == utr)
        )
        if result.scalar_one_or_none():
            await message.answer(
                "❌ <b>Duplicate UTR!</b>\n\n"
                "This UTR number has already been used. "
                "If this is an error, please contact admin.",
                reply_markup=home_keyboard()
            )
            await state.clear()
            return

    await save_payment(message, state, utr_number=utr, screenshot_file_id=None)


# ─── Receive Screenshot ───────────────────────────────────────────────────────

@router.message(MockInterviewStates.utr_or_screenshot, F.photo)
async def receive_payment_screenshot(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await save_payment(message, state, utr_number=None, screenshot_file_id=photo.file_id)


@router.message(MockInterviewStates.utr_or_screenshot, F.document)
async def receive_payment_document(message: Message, state: FSMContext):
    doc = message.document
    await save_payment(message, state, utr_number=None, screenshot_file_id=doc.file_id)


@router.message(MockInterviewStates.utr_or_screenshot)
async def invalid_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("proof_type") == "utr":
        await message.answer("❌ Please enter the UTR number as text:")
    else:
        await message.answer("❌ Please upload a photo or PDF screenshot:")


# ─── Save Payment ─────────────────────────────────────────────────────────────

async def save_payment(
    message: Message,
    state: FSMContext,
    utr_number: str | None,
    screenshot_file_id: str | None,
):
    data = await state.get_data()
    user = message.from_user

    expiry = datetime.fromisoformat(data.get("payment_expiry", datetime.utcnow().isoformat()))

    payment = MockPayment(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        amount=data.get("price", settings.DEFAULT_MOCK_PRICE),
        upi_id_used=data.get("upi_id", settings.DEFAULT_UPI_ID),
        utr_number=utr_number,
        screenshot_file_id=screenshot_file_id,
        payment_status="pending",
        expiry_at=expiry,
    )

    async with AsyncSessionLocal() as session:
        session.add(payment)
        await session.commit()
        await session.refresh(payment)

    await message.answer(
        "✅ <b>Payment details submitted!</b>\n\n"
        "Our admin team will verify your payment shortly.\n"
        "You will be notified once verified.\n\n"
        "⏳ <i>Verification usually takes a few minutes.</i>",
        reply_markup=home_keyboard()
    )

    # Notify admin group
    await notify_admin_payment(message.bot, payment)
    await state.clear()


async def notify_admin_payment(bot, payment: MockPayment):
    """Send payment request to admin group"""
    if not settings.ADMIN_GROUP_ID:
        return

    try:
        admin_msg = format_payment_admin(payment)
        keyboard = admin_payment_keyboard(payment.id)

        if payment.screenshot_file_id:
            await bot.send_photo(
                settings.ADMIN_GROUP_ID,
                photo=payment.screenshot_file_id,
                caption=admin_msg,
                reply_markup=keyboard,
            )
        else:
            await bot.send_message(
                settings.ADMIN_GROUP_ID,
                admin_msg,
                reply_markup=keyboard,
            )
    except Exception as e:
        logger.error(f"Failed to notify admin about payment: {e}")


# ─── Admin Payment Approval (from group) ─────────────────────────────────────

@router.callback_query(F.data.startswith("approve_payment_"))
async def approve_payment(callback: CallbackQuery):
    payment_id = int(callback.data.split("_")[2])
    admin = callback.from_user

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MockPayment).where(MockPayment.id == payment_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            await callback.answer("Payment not found.", show_alert=True)
            return

        if payment.payment_status != "pending":
            await callback.answer(
                f"Already {payment.payment_status}!", show_alert=True
            )
            return

        payment.payment_status = "approved"
        payment.approved_by = admin.id
        payment.approved_by_name = admin.full_name
        await session.commit()

    # Notify user
    try:
        await callback.bot.send_message(
            payment.user_id,
            "✅ <b>Payment Verified Successfully!</b>\n\n"
            "Your mock interview will be scheduled shortly.\n"
            "We will inform you about the date and time.",
        )
    except Exception:
        pass

    # Update admin message
    new_text = (
        f"✅ <b>APPROVED</b> by @{admin.username or admin.full_name}\n\n"
        + format_payment_admin(payment)
    )
    try:
        await callback.message.edit_caption(new_text)
    except Exception:
        await callback.message.edit_text(new_text)

    await callback.answer("✅ Payment approved!")


@router.callback_query(F.data.startswith("decline_payment_"))
async def decline_payment(callback: CallbackQuery):
    payment_id = int(callback.data.split("_")[2])
    admin = callback.from_user

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MockPayment).where(MockPayment.id == payment_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            await callback.answer("Payment not found.", show_alert=True)
            return

        if payment.payment_status != "pending":
            await callback.answer(
                f"Already {payment.payment_status}!", show_alert=True
            )
            return

        payment.payment_status = "declined"
        payment.approved_by = admin.id
        payment.approved_by_name = admin.full_name
        await session.commit()

    # Notify user
    try:
        await callback.bot.send_message(
            payment.user_id,
            "❌ <b>Payment Verification Failed</b>\n\n"
            "Your payment could not be verified.\n"
            "Please contact support with your payment proof.",
        )
    except Exception:
        pass

    new_text = (
        f"❌ <b>DECLINED</b> by @{admin.username or admin.full_name}\n\n"
        + format_payment_admin(payment)
    )
    try:
        await callback.message.edit_caption(new_text)
    except Exception:
        await callback.message.edit_text(new_text)

    await callback.answer("❌ Payment declined.")
