"""
Loads environment variables and defines configuration settings for the bot.
- Reads API keys, bot token, paths to data files, and other settings from the .env file.
- Sets up basic logging for the application.
"""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"

if ENV_FILE_PATH.exists():
    load_dotenv(ENV_FILE_PATH)
else:
    print(f"Warning: .env file not found at {ENV_FILE_PATH}. "
          "Ensure environment variables are set externally if this is a production environment.")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set. Please create a .env file or set it externally.")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")
OPENAI_API_BASE_URL = os.getenv("OPENAI_API_BASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SEARCH_MODEL_NAME = os.getenv("SEARCH_MODEL_NAME", "gpt-4o-mini")
ANSWER_MODEL_NAME = os.getenv("ANSWER_MODEL_NAME", "gpt-4o-mini")

USING_OPENAI_DIRECTLY = bool(OPENAI_API_KEY)

try:
    BOSS_ID = int(os.getenv("BOSS_ID")) if os.getenv("BOSS_ID") else None
except ValueError:
    print("Warning: BOSS_ID is not a valid integer. Critical notifications might not work.")
    BOSS_ID = None

SHELF_FILE_PATH_STR = os.getenv("SHELF_FILE_PATH", "data/chat_configs.shelf")
DEFAULT_SETTINGS_FILE_PATH_STR = os.getenv("DEFAULT_SETTINGS_FILE_PATH", "data/default_settings.json")
PROMPTS_DIR_PATH_STR = os.getenv("PROMPTS_DIR_PATH", "data/prompts/")
GSPREAD_KEY_FILE_PATH_STR = os.getenv("GSPREAD_KEY_FILE_PATH", "data/gspread_key.json")

SHELF_FILE_PATH = BASE_DIR / SHELF_FILE_PATH_STR
DEFAULT_SETTINGS_FILE_PATH = BASE_DIR / DEFAULT_SETTINGS_FILE_PATH_STR
PROMPTS_DIR_PATH = BASE_DIR / PROMPTS_DIR_PATH_STR
GSPREAD_KEY_FILE_PATH = BASE_DIR / GSPREAD_KEY_FILE_PATH_STR

USER_GROUP_LINKS_SHELF_KEY = "user_group_links"

LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MAX_MENTIONS_PER_CHAT = 10

GSPREAD_SERVICE_ACCOUNT_EMAIL = None
try:
    with open(GSPREAD_KEY_FILE_PATH, 'r') as f:
        import json
        gspread_key_data = json.load(f)
        GSPREAD_SERVICE_ACCOUNT_EMAIL = gspread_key_data.get("client_email")
        if not GSPREAD_SERVICE_ACCOUNT_EMAIL:
            logger.warning(f"Client email not found in GSpread key file at {GSPREAD_KEY_FILE_PATH}. GSpread functionality may be limited.")
except FileNotFoundError:
    logger.warning(f"GSpread key file not found at {GSPREAD_KEY_FILE_PATH}. GSpread functionality may be limited.")
except json.JSONDecodeError:
    logger.error(f"Error decoding GSpread key file at {GSPREAD_KEY_FILE_PATH}. Ensure it's valid JSON.")

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
if not PROMPTS_DIR_PATH.is_dir():
    logger.error(
        f"Prompts directory not found at {PROMPTS_DIR_PATH}. "
        "LLM functionalities requiring prompts will fail."
    )

logger.info("Configuration loaded.")
