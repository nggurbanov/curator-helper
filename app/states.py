"""
Defines FSM (Finite State Machine) states using aiogram.fsm.state.State and StatesGroup.
Used for multi-step operations, dialogs, or managing user/chat-specific states.
"""

from aiogram.fsm.state import State, StatesGroup

class AdminSetSheet(StatesGroup):
    """States for the /setfaqsheet command flow."""
    waiting_for_gsheet_url = State()

class AdminSetPersonality(StatesGroup):
    """States for the /setpersonalityprompt command flow."""
    waiting_for_prompt_text = State()
    confirming_prompt = State()

class AdminSetWelcome(StatesGroup):
    """States for the /setwelcomemessage command flow."""
    waiting_for_welcome_text = State()
    confirming_welcome = State()
    
class AdminSetErrorMsg(StatesGroup):
    """States for the /seterror command flow."""
    waiting_for_error_text = State()
    confirming_error_msg = State()

class AdminAddMention(StatesGroup):
    """States for the /addmention command flow."""
    waiting_for_mention_text = State()
    confirming_mention = State()
