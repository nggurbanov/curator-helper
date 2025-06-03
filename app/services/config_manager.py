"""
Manages chat-specific configurations using a shelve file for persistence
and a JSON file for default settings.

Responsibilities:
- Loading default settings from data/default_settings.json.
- Retrieving the configuration for a specific chat_id (merging with defaults).
- Updating/saving the configuration for a specific chat_id in the shelve file.
- Managing the gsheet_sync_conflict flag for each chat.
"""

import shelve
import json
import logging
import threading
from typing import Dict, Any, Optional
from app import config

logger = logging.getLogger(__name__)

_default_settings: Optional[Dict[str, Any]] = None
_default_settings_lock = threading.Lock()

def _load_default_settings() -> Dict[str, Any]:
    """
    Loads default settings from the JSON file specified in app.config.
    This function is intended for internal use and ensures defaults are loaded once.
    """
    global _default_settings
    if _default_settings is None:
        with _default_settings_lock:
            if _default_settings is None:
                try:
                    with open(config.DEFAULT_SETTINGS_FILE_PATH, 'r', encoding='utf-8') as f:
                        _default_settings = json.load(f)
                    logger.info(f"Default settings loaded successfully from {config.DEFAULT_SETTINGS_FILE_PATH}")
                except FileNotFoundError:
                    logger.error(f"CRITICAL: Default settings file not found at {config.DEFAULT_SETTINGS_FILE_PATH}. Bot may not function correctly.")
                    _default_settings = {}
                except json.JSONDecodeError:
                    logger.error(f"CRITICAL: Error decoding JSON from default settings file {config.DEFAULT_SETTINGS_FILE_PATH}.")
                    _default_settings = {}
                except Exception as e:
                    logger.error(f"CRITICAL: An unexpected error occurred while loading default settings: {e}")
                    _default_settings = {}
    return _default_settings


def get_default_settings() -> Dict[str, Any]:
    """Returns a copy of the default settings."""
    return _load_default_settings().copy()


_shelf_lock = threading.Lock()

def get_chat_config(chat_id: int) -> Dict[str, Any]:
    """
    Retrieves the configuration for a specific chat_id.
    If the chat_id is not found in the shelve file or a setting is missing,
    it merges with default settings.

    Args:
        chat_id: The ID of the chat.

    Returns:
        A dictionary containing the complete configuration for the chat.
    """
    chat_id_str = str(chat_id)
    defaults = get_default_settings()
    chat_specific_config = {}

    try:
        with _shelf_lock:
            with shelve.open(str(config.SHELF_FILE_PATH)) as shelf:
                if chat_id_str in shelf:
                    chat_specific_config = shelf[chat_id_str]
                else:
                    logger.info(f"No specific configuration found for chat_id {chat_id}. Using defaults.")
    except Exception as e:
        logger.error(f"Error reading from shelve file for chat_id {chat_id}: {e}. Using defaults.")
    
    final_config = defaults.copy()
    final_config.update(chat_specific_config)
    
    return final_config

def update_chat_config(chat_id: int, new_config: Dict[str, Any]) -> bool:
    """
    Updates and saves the entire configuration dictionary for a specific chat_id
    to the shelve file.

    Args:
        chat_id: The ID of the chat.
        new_config: The complete new configuration dictionary for the chat.

    Returns:
        True if successful, False otherwise.
    """
    chat_id_str = str(chat_id)
    try:
        with _shelf_lock:
            with shelve.open(str(config.SHELF_FILE_PATH), writeback=False) as shelf:
                shelf[chat_id_str] = new_config
        logger.info(f"Configuration updated successfully for chat_id {chat_id}.")
        return True
    except Exception as e:
        logger.error(f"Error writing to shelve file for chat_id {chat_id}: {e}")
        return False

def set_chat_setting(chat_id: int, key: str, value: Any) -> bool:
    """
    Updates a single setting for a specific chat_id in the shelve file.
    Loads existing config, updates the key, then saves.

    Args:
        chat_id: The ID of the chat.
        key: The configuration key to update.
        value: The new value for the configuration key.

    Returns:
        True if successful, False otherwise.
    """
    chat_id_str = str(chat_id)
    try:
        with _shelf_lock:
            with shelve.open(str(config.SHELF_FILE_PATH), writeback=False) as shelf:
                current_chat_config = shelf.get(chat_id_str, {})
                current_chat_config[key] = value
                shelf[chat_id_str] = current_chat_config
        logger.info(f"Setting '{key}' updated successfully for chat_id {chat_id}.")
        return True
    except Exception as e:
        logger.error(f"Error updating setting '{key}' in shelve for chat_id {chat_id}: {e}")
        return False

def delete_chat_config(chat_id: int) -> bool:
    """
    Deletes the entire configuration for a specific chat_id from the shelve file.
    Useful if a bot is removed from a chat and settings should be cleaned up.

    Args:
        chat_id: The ID of the chat.

    Returns:
        True if successful or if the key didn't exist, False on error.
    """
    chat_id_str = str(chat_id)
    try:
        with _shelf_lock:
            with shelve.open(str(config.SHELF_FILE_PATH)) as shelf:
                if chat_id_str in shelf:
                    del shelf[chat_id_str]
                    logger.info(f"Configuration deleted successfully for chat_id {chat_id}.")
                else:
                    logger.info(f"No configuration found to delete for chat_id {chat_id}.")
        return True
    except Exception as e:
        logger.error(f"Error deleting configuration from shelve for chat_id {chat_id}: {e}")
        return False

def get_all_chat_ids() -> list[int]:
    """Returns a list of all chat_ids that have configurations in the shelf."""
    shelf_path = str(config.SHELF_FILE_PATH)
    chat_ids = []
    try:
        with shelve.open(shelf_path) as db:
            for key in db.keys():
                if isinstance(key, str) and key.lstrip('-').isdigit():
                    try:
                        chat_ids.append(int(key))
                    except ValueError:
                        logger.warning(f"Found non-integer key '{key}' in shelf while expecting chat_ids.")
                elif key == config.USER_GROUP_LINKS_SHELF_KEY:
                    continue

    except FileNotFoundError:
        logger.error(f"Shelf file not found at {shelf_path} when trying to get all chat IDs.")
    except Exception as e:
        logger.error(f"Error reading chat IDs from shelf {shelf_path}: {e}", exc_info=True)
    logger.debug(f"Retrieved known chat_ids: {chat_ids}")
    return chat_ids

_load_default_settings()

if __name__ == '__main__':
    
    print("Default Settings:", get_default_settings())

    test_chat_id = 12345
    
    initial_conf = get_chat_config(test_chat_id)
    print(f"\nInitial config for chat {test_chat_id}:", initial_conf)

    print(f"\nUpdating 'gsheet_url' for chat {test_chat_id}...")
    if set_chat_setting(test_chat_id, "gsheet_url", "https://new.example.com/sheet"):
        updated_conf = get_chat_config(test_chat_id)
        print(f"Updated config for chat {test_chat_id}:", updated_conf)
    else:
        print("Failed to update setting.")

    print(f"\nSetting 'gsheet_sync_conflict' to True for chat {test_chat_id}...")
    if set_chat_setting(test_chat_id, "gsheet_sync_conflict", True):
        conflict_conf = get_chat_config(test_chat_id)
        print(f"Config with conflict for chat {test_chat_id}:", conflict_conf)
    else:
        print("Failed to set conflict flag.")

    new_full_config = {
        "gsheet_url": "https://another.example.com/sheet",
        "personality_prompt_name": "custom_prompt.txt",
        "welcome_message": "A custom welcome!",
        "mentions": ["mybot"],
        "error_message_non_admin": "Admins only, please.",
        "anonq_enabled": False,
        "gsheet_sync_conflict": False,
        "new_custom_setting": "hello world"
    }
    print(f"\nUpdating full config for chat {test_chat_id}...")
    if update_chat_config(test_chat_id, new_full_config):
        full_updated_conf = get_chat_config(test_chat_id)
        print(f"Full updated config for chat {test_chat_id}:", full_updated_conf)
    else:
        print("Failed to update full config.")
    
    # print(f"\nDeleting config for chat {test_chat_id}...")
    # if delete_chat_config(test_chat_id):
    #     deleted_conf = get_chat_config(test_chat_id)
    #     print(f"Config after deletion for chat {test_chat_id}:", deleted_conf)
    # else:
    #     print("Failed to delete config.")
