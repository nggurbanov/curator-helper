"""
General utility functions used across the application.
- Emoji remover.
- Chat administrator check.
- Other helper functions.
"""
import logging
import emoji
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from typing import Optional

logger = logging.getLogger(__name__)

def remove_emojis(text: str) -> str:
    """
    Removes all emoji characters from a given string.

    Args:
        text: The input string.

    Returns:
        The string with emojis removed.
    """
    if not text:
        return ""
    return emoji.replace_emoji(text, replace='')

async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Checks if a given user is an administrator or creator of a specific chat.

    Args:
        bot: The Aiogram Bot instance.
        chat_id: The ID of the chat.
        user_id: The ID of the user to check.

    Returns:
        True if the user is an admin or creator, False otherwise.
    """
    if not chat_id or not user_id:
        return False
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except TelegramAPIError as e:
        logger.error(f"TelegramAPIError while checking admin status for user {user_id} in chat {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while checking admin status for user {user_id} in chat {chat_id}: {e}")
        return False

def get_user_mention_html(user_id: int, name: str) -> str:
    """
    Creates an HTML mention link for a user.

    Args:
        user_id: The Telegram user ID.
        name: The display name for the user.

    Returns:
        An HTML string for mentioning the user.
    """
    safe_name = name.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def format_reply_text(text: str, bot_name: Optional[str] = None) -> str:
    """
    Basic formatting for bot replies. Could be expanded.
    Removes emojis and potentially adds bot signature if desired.
    """
    cleaned_text = remove_emojis(text)
    return cleaned_text


if __name__ == '__main__':
    text_with_emojis = "Hello 👋 World 🌎! This is a test 😊."
    text_without_emojis = remove_emojis(text_with_emojis)
    print(f"Original: {text_with_emojis}")
    print(f"Cleaned: {text_without_emojis}")
    assert "👋" not in text_without_emojis

    print("\nTo test is_chat_admin, run it within an Aiogram handler or with a mock Bot object.")

    print(f"\nUser mention: {get_user_mention_html(123456789, 'Test User <HTML>')}")
