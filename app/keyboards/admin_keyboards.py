# app/keyboards/admin_keyboards.py
"""
Contains functions that generate InlineKeyboardMarkup objects specifically for
administrative command flows.
Examples:
- Confirmation/cancel keyboards for settings changes.
- Keyboard for /editmentions (listing mentions with delete buttons).
- Keyboard for /refresh conflict resolution choices.
"""
from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Callback data prefixes or constants
# For settings confirmation
CALLBACK_ADMIN_CONFIRM_SETTING = "admin_confirm_setting:" # Append setting name & chat_id
CALLBACK_ADMIN_CANCEL_SETTING = "admin_cancel_setting:"   # Append setting name & chat_id

# For /editmentions
CALLBACK_ADMIN_DELETE_MENTION = "admin_del_mention" # Ensure this is defined

# For /refresh conflict resolution
CALLBACK_ADMIN_CONFLICT_PUSH = "admin_conflict_push" # chat_id will be in callback_data if needed or from context
CALLBACK_ADMIN_CONFLICT_PULL = "admin_conflict_pull"

def get_setting_confirmation_keyboard(setting_name: str, temp_value: Any, chat_id: int) -> InlineKeyboardMarkup:
    """
    Generates a confirm/cancel keyboard for a setting change.
    Stores temporary value or identifier in callback data if needed, or rely on FSM state.
    For simplicity, we might just confirm the action, assuming FSM holds the temp value.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirm", callback_data=f"{CALLBACK_ADMIN_CONFIRM_SETTING}{setting_name}:{chat_id}")
    builder.button(text="❌ Cancel", callback_data=f"{CALLBACK_ADMIN_CANCEL_SETTING}{setting_name}:{chat_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_edit_mentions_keyboard(chat_id: int, mentions: list): # Type hint 'list'
    builder = InlineKeyboardBuilder()

    # Add a type check for robustness
    if not isinstance(mentions, list):
        # Log this error, as it indicates a problem with how data is stored/retrieved
        # logger.error(f"get_edit_mentions_keyboard received non-list for mentions in chat {chat_id}: {type(mentions)}")
        # Consider returning an empty keyboard or a keyboard with an error message button
        return builder.as_markup() # Return empty keyboard

    if not mentions:
        return builder.as_markup() # Return empty keyboard if list is empty

    for mention_item in mentions:
        # Ensure mention_item is a dictionary before trying to .get()
        if not isinstance(mention_item, dict):
            # logger.warning(f"Skipping non-dict item in mentions list for chat {chat_id}: {mention_item}")
            continue 

        username = mention_item.get('username', 'Unknown')
        description = mention_item.get('description', '')
        display_text = f"❌ {username}"
        if description:
            display_text += f" ({description[:20]})" 
        
        callback_data_mention = f"{CALLBACK_ADMIN_DELETE_MENTION}:{chat_id}:{(str(username))}" # Escape username for callback data
        builder.row(InlineKeyboardButton(text=display_text, callback_data=callback_data_mention))
    
    return builder.as_markup()

def get_refresh_conflict_resolution_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """
    Generates the keyboard for resolving GSheet sync conflicts during /refresh.
    """
    builder = InlineKeyboardBuilder()
    # Pass chat_id in callback if needed, though handler might get it from message context
    builder.button(text="Use Bot's Settings & Update GSheet", callback_data=f"{CALLBACK_ADMIN_CONFLICT_PUSH}:{chat_id}")
    builder.button(text="Use GSheet Settings & Update Bot", callback_data=f"{CALLBACK_ADMIN_CONFLICT_PULL}:{chat_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_toggle_confirmation_keyboard(setting_name: str, current_status: bool, chat_id: int) -> InlineKeyboardMarkup:
    """
    Generic keyboard for toggling a boolean setting (e.g., anonq_enabled).
    Shows the action that will be taken.
    """
    action_text = "Disable" if current_status else "Enable"
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ {action_text} {setting_name}", callback_data=f"{CALLBACK_ADMIN_CONFIRM_SETTING}toggle_{setting_name}:{chat_id}")
    builder.button(text="❌ Cancel", callback_data=f"{CALLBACK_ADMIN_CANCEL_SETTING}toggle_{setting_name}:{chat_id}")
    builder.adjust(1)
    return builder.as_markup()


if __name__ == '__main__':
    print("Example Admin Keyboards JSON (for understanding):")
    
    confirm_kb = get_setting_confirmation_keyboard("personality", "new_prompt_text_placeholder", 123)
    # print("\nConfirm Setting Keyboard:")
    # print(confirm_kb.model_dump_json(indent=2))
    for row in confirm_kb.inline_keyboard:
        for button in row:
            print(f"Text: {button.text}, Callback Data: {button.callback_data}")


    mentions_kb = get_edit_mentions_keyboard(123, ["bothelp", "adminbot", "faqmaster"])
    # print("\nEdit Mentions Keyboard:")
    # print(mentions_kb.model_dump_json(indent=2))
    for row in mentions_kb.inline_keyboard:
        for button in row:
            print(f"Text: {button.text}, Callback Data: {button.callback_data}")

    conflict_kb = get_refresh_conflict_resolution_keyboard(123)
    # print("\nConflict Resolution Keyboard:")
    # print(conflict_kb.model_dump_json(indent=2))
    for row in conflict_kb.inline_keyboard:
        for button in row:
            print(f"Text: {button.text}, Callback Data: {button.callback_data}")
    
    toggle_kb = get_toggle_confirmation_keyboard("anonq", True, 123) # Example: anonq is currently True
    # print("\nToggle Confirmation Keyboard:")
    # print(toggle_kb.model_dump_json(indent=2))
    for row in toggle_kb.inline_keyboard:
        for button in row:
            print(f"Text: {button.text}, Callback Data: {button.callback_data}")
