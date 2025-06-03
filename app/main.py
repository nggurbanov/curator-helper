"""
Main entry point for the Telegram bot.
- Initializes Aiogram Bot and Dispatcher.
- Loads configurations from app.config.
- Initializes and registers routers/handlers from the app.handlers package.
- Initializes instances of service classes (ConfigManager, GSheetService, LLMService).
- Contains the main() async function and starts the bot's polling loop.
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.bot import DefaultBotProperties

from app import config as global_config
from app.handlers import admin_router, user_router
from app.services import config_manager
from app.services.gsheet_service import GSheetService
from app.services.llm_service import LLMService
from app.services.user_group_link_service import UserGroupLinkService

logger = logging.getLogger(__name__)

async def main():
    """
    Initializes and starts the Telegram bot.
    """
    logger.info("Starting bot...")

    storage = MemoryStorage()

    bot = Bot(token=global_config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)

    gsheet_service_instance = GSheetService(credentials_path=str(global_config.GSPREAD_KEY_FILE_PATH))
    llm_service_instance = LLMService()
    user_group_link_service_instance = UserGroupLinkService(
        shelf_file_path=str(global_config.SHELF_FILE_PATH),
        shelf_key=global_config.USER_GROUP_LINKS_SHELF_KEY
    )

    dp["gsheet_service_instance"] = gsheet_service_instance
    dp["llm_service_instance"] = llm_service_instance
    dp["user_group_link_service"] = user_group_link_service_instance

    dp.include_router(admin_router)
    dp.include_router(user_router)
    logger.info("Message and callback handlers registered.")

    try:
        logger.info("Bot started polling.")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Bot shutting down...")
        await bot.session.close()
        logger.info("Bot session closed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot polling stopped by user.")
    except Exception as e:
        logger.critical(f"Critical error during bot execution: {e}", exc_info=True)
