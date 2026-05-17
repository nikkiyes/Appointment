"""
Start handler - main menu and home navigation
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from keyboards import main_menu_keyboard

router = Router()
logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 <b>Welcome to Interview Management Bot!</b>\n\n"
    "🎓 This bot helps you manage your interview process efficiently.\n\n"
    "Please select an option below to get started:"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command"""
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "home")
async def go_home(callback: CallbackQuery, state: FSMContext):
    """Return to main menu"""
    await state.clear()
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Cancel current action"""
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Action cancelled.</b>\n\nReturning to main menu...",
        reply_markup=main_menu_keyboard()
    )
    await callback.answer("Cancelled")


@router.callback_query(F.data == "check_join")
async def check_channel_join(callback: CallbackQuery):
    """Re-check channel join status"""
    await callback.answer("✅ Access granted! Please use the bot now.", show_alert=True)
    from keyboards import main_menu_keyboard
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    """Back to admin menu"""
    from keyboards import admin_main_keyboard
    await callback.message.edit_text(
        "🔐 <b>Admin Panel</b>\n\nSelect an option:",
        reply_markup=admin_main_keyboard()
    )
    await callback.answer()
