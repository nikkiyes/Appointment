"""
FSM States for all conversation flows
"""

from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    """Interview booking flow states"""
    full_name = State()
    roll_number = State()
    sib = State()
    date_range = State()
    introduction = State()
    preferred_date = State()
    screenshot = State()
    confirm = State()


class MockInterviewStates(StatesGroup):
    """Mock interview payment flow"""
    confirm_info = State()
    payment_pending = State()
    payment_proof = State()
    utr_or_screenshot = State()


class AdminStates(StatesGroup):
    """Admin panel states"""
    password = State()
    main_menu = State()
    
    # Search
    search_query = State()
    
    # Schedule
    select_student = State()
    set_date = State()
    set_time = State()
    
    # Meet link
    select_student_meet = State()
    enter_meet_link = State()
    
    # Broadcast
    broadcast_message = State()
    
    # Payment settings
    set_price = State()
    set_upi = State()
    set_payee = State()
    
    # View students pagination
    viewing_students = State()


class PaymentVerifyStates(StatesGroup):
    """Payment verification by admin"""
    viewing = State()
