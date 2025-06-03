# app/config.py
"""
Loads environment variables and defines configuration settings for the bot.
- Reads API keys, bot token, paths to data files, and other settings from the .env file.
- Sets up basic logging for the application.
"""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# Assuming .env is in the project root, which is one level above the 'app' directory.
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"

if ENV_FILE_PATH.exists():
    load_dotenv(ENV_FILE_PATH)
else:
    # Fallback for environments where .env might not be present (e.g., some deployment scenarios)
    # In such cases, environment variables are expected to be set directly in the environment.
    print(f"Warning: .env file not found at {ENV_FILE_PATH}. "
          "Ensure environment variables are set externally if this is a production environment.")

# --- Telegram Bot Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set. Please create a .env file or set it externally.")

# --- LLM API Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY") # Optional
OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL") # Optional, for custom endpoints like DeepInfra
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SEARCH_MODEL_NAME = os.getenv("SEARCH_MODEL_NAME", "gpt-4o-mini")
ANSWER_MODEL_NAME = os.getenv("ANSWER_MODEL_NAME", "gpt-4o-mini")

# Determine which AI client to primarily use (OpenAI or a compatible one)
# This logic can be refined in llm_service.py
USING_OPENAI_DIRECTLY = bool(OPENAI_API_KEY)

# --- Bot Admin/Owner ---
try:
    BOSS_ID = int(os.getenv("BOSS_ID")) if os.getenv("BOSS_ID") else None
except ValueError:
    print("Warning: BOSS_ID is not a valid integer. Critical notifications might not work.")
    BOSS_ID = None


# --- Data File Paths (relative to project root) ---
# These paths are read from .env, allowing flexibility if you move the data dir
SHELF_FILE_PATH_STR = os.getenv("SHELF_FILE_PATH", "data/chat_configs.shelf")
DEFAULT_SETTINGS_FILE_PATH_STR = os.getenv("DEFAULT_SETTINGS_FILE_PATH", "data/default_settings.json")
PROMPTS_DIR_PATH_STR = os.getenv("PROMPTS_DIR_PATH", "data/prompts/")
GSPREAD_KEY_FILE_PATH_STR = os.getenv("GSPREAD_KEY_FILE_PATH", "data/gspread_key.json")
# USER_GROUP_LINKS_FILE_PATH_STR = os.getenv("USER_GROUP_LINKS_FILE_PATH", "data/user_group_links.json") # Removed

# Convert string paths to Path objects for easier manipulation
SHELF_FILE_PATH = BASE_DIR / SHELF_FILE_PATH_STR
DEFAULT_SETTINGS_FILE_PATH = BASE_DIR / DEFAULT_SETTINGS_FILE_PATH_STR
PROMPTS_DIR_PATH = BASE_DIR / PROMPTS_DIR_PATH_STR
GSPREAD_KEY_FILE_PATH = BASE_DIR / GSPREAD_KEY_FILE_PATH_STR
# USER_GROUP_LINKS_FILE_PATH = BASE_DIR / USER_GROUP_LINKS_FILE_PATH_STR # Removed

# --- Shelf Keys (if you want to centralize them) ---
USER_GROUP_LINKS_SHELF_KEY = "user_group_links" # Added for clarity

# --- Logging Configuration ---
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO) # Defaults to INFO if invalid

# Basic logging setup
# You can expand this with file logging, formatting, etc.
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler() # Log to console
        # You might want to add a FileHandler here for persistent logs
        # logging.FileHandler(BASE_DIR / "app.log")
    ]
)
logger = logging.getLogger(__name__)

# --- GSpread Configuration ---
# GSpread client will be initialized in gsheet_service.py using GSPREAD_KEY_FILE_PATH

# --- Other Global Settings (can be moved to default_settings.json if preferred) ---
# Example: Maximum number of mentions a chat can have
MAX_MENTIONS_PER_CHAT = 10

GSPREAD_SERVICE_ACCOUNT_EMAIL = None
try:
    # GSPREAD_KEY_FILE_PATH is defined earlier in the file
    with open(GSPREAD_KEY_FILE_PATH, 'r') as f:
        import json # Import json here if not already at the top of the file
        gspread_key_data = json.load(f)
        GSPREAD_SERVICE_ACCOUNT_EMAIL = gspread_key_data.get("client_email")
        if not GSPREAD_SERVICE_ACCOUNT_EMAIL:
            logger.warning(f"Client email not found in GSpread key file at {GSPREAD_KEY_FILE_PATH}. GSpread functionality may be limited.")
except FileNotFoundError:
    logger.warning(f"GSpread key file not found at {GSPREAD_KEY_FILE_PATH}. GSpread functionality may be limited.")
except json.JSONDecodeError:
    logger.error(f"Error decoding GSpread key file at {GSPREAD_KEY_FILE_PATH}. Ensure it's valid JSON.")

# Placeholder for any other global bot settings
# For instance, if you had global flags from your old config.py that aren't per-chat:
# REPLY_CONTEXT_GLOBALLY_ENABLED = True # Example

# --- Validate essential paths ---
if not GSPREAD_KEY_FILE_PATH.exists():
    logger.warning(
        f"GSpread key file not found at {GSPREAD_KEY_FILE_PATH}. "
        "Google Sheets integration will fail."
    )
if not DEFAULT_SETTINGS_FILE_PATH.exists():
    logger.error(
        f"Default settings JSON file not found at {DEFAULT_SETTINGS_FILE_PATH}. "
        "The bot may not function correctly without default configurations."
    )
    # Depending on how critical this is, you might raise an error or try to proceed with hardcoded minimal defaults.
if not PROMPTS_DIR_PATH.is_dir():
    logger.error(
        f"Prompts directory not found at {PROMPTS_DIR_PATH}. "
        "LLM functionalities requiring prompts will fail."
    )

logger.info("Configuration loaded.")

# You can add a function here to print loaded config for debugging if needed
# def print_loaded_config():
#     logger.debug(f"BOT_TOKEN: {'*' * 5 if BOT_TOKEN else 'Not Set'}")
#     logger.debug(f"OPENAI_API_KEY: {'*' * 5 if OPENAI_API_KEY else 'Not Set'}")
#     logger.debug(f"SHELF_FILE_PATH: {SHELF_FILE_PATH}")
#     # ... and so on for other important configs

# if LOG_LEVEL == logging.DEBUG:
# print_loaded_config()
