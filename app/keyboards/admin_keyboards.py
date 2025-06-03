from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

CALLBACK_ADMIN_CONFIRM_SETTING = "admin_confirm_setting:"
CALLBACK_ADMIN_CANCEL_SETTING = "admin_cancel_setting:"
CALLBACK_ADMIN_DELETE_MENTION = "admin_del_mention"
CALLBACK_ADMIN_CONFLICT_PUSH = "admin_conflict_push"
CALLBACK_ADMIN_CONFLICT_PULL = "admin_conflict_pull"

def get_setting_confirmation_keyboard(setting_name: str, temp_value: Any, chat_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirm", callback_data=f"{CALLBACK_ADMIN_CONFIRM_SETTING}{setting_name}:{chat_id}")
    builder.button(text="❌ Cancel", callback_data=f"{CALLBACK_ADMIN_CANCEL_SETTING}{setting_name}:{chat_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_edit_mentions_keyboard(chat_id: int, mentions: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not isinstance(mentions, list):
        return builder.as_markup()
    if not mentions:
        return builder.as_markup()
    for mention_item in mentions:
        if not isinstance(mention_item, dict):
            continue
        username = mention_item.get('username', 'Unknown')
        description = mention_item.get('description', '')
        display_text = f"❌ {username}"
        if description:
            display_text += f" ({description[:20]})"
        callback_data_mention = f"{CALLBACK_ADMIN_DELETE_MENTION}:{chat_id}:{username}"
        builder.row(InlineKeyboardButton(text=display_text, callback_data=callback_data_mention))
    return builder.as_markup()

def get_refresh_conflict_resolution_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Use Bot's Settings & Update GSheet", callback_data=f"{CALLBACK_ADMIN_CONFLICT_PUSH}:{chat_id}")
    builder.button(text="Use GSheet Settings & Update Bot", callback_data=f"{CALLBACK_ADMIN_CONFLICT_PULL}:{chat_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_toggle_confirmation_keyboard(setting_name: str, current_status: bool, chat_id: int) -> InlineKeyboardMarkup:
    action_text = "Disable" if current_status else "Enable"
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ {action_text} {setting_name}", callback_data=f"{CALLBACK_ADMIN_CONFIRM_SETTING}toggle_{setting_name}:{chat_id}")
    builder.button(text="❌ Cancel", callback_data=f"{CALLBACK_ADMIN_CANCEL_SETTING}toggle_{setting_name}:{chat_id}")
    builder.adjust(1)
    return builder.as_markup()


if __name__ == '__main__':
    print("Example Admin Keyboards JSON (for understanding):")
    confirm_kb = get_setting_confirmation_keyboard("personality", "new_prompt_text_placeholder", 123)
    for row in confirm_kb.inline_keyboard:
        for button in row:
            print(f"Text: {button.text}, Callback Data: {button.callback_data}")
    mentions_kb = get_edit_mentions_keyboard(123, ["bothelp", "adminbot", "faqmaster"])
    for row in mentions_kb.inline_keyboard:
        for button in row:
            print(f"Text: {button.text}, Callback Data: {button.callback_data}")
    conflict_kb = get_refresh_conflict_resolution_keyboard(123)
    for row in conflict_kb.inline_keyboard:
        for button in row:
            print(f"Text: {button.text}, Callback Data: {button.callback_data}")
    toggle_kb = get_toggle_confirmation_keyboard("anonq", True, 123)
    for row in toggle_kb.inline_keyboard:
        for button in row:
            print(f"Text: {button.text}, Callback Data: {button.callback_data}")
