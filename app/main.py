# app/main.py
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
from aiogram.fsm.storage.memory import MemoryStorage # Example storage, consider Redis for production
# from aiogram.fsm.storage.redis import RedisStorage # For production
from aiogram.client.bot import DefaultBotProperties

from app import config as global_config # Renamed to avoid conflict with local 'config' module
from app.handlers import admin_router, user_router
from app.services import config_manager # Already loads defaults on import
from app.services.gsheet_service import GSheetService
from app.services.llm_service import LLMService
from app.services.user_group_link_service import UserGroupLinkService
# from app.middlewares import SomeMiddleware # Example if you add middlewares

logger = logging.getLogger(__name__)

async def main():
    """
    Initializes and starts the Telegram bot.
    """
    logger.info("Starting bot...")

    # --- Initialize FSM Storage ---
    # For simple cases or testing, MemoryStorage is fine.
    # For production, consider RedisStorage or another persistent FSM storage.
    storage = MemoryStorage()
    # storage = RedisStorage.from_url("redis://localhost:6379/0") # Example for Redis

    # --- Initialize Bot and Dispatcher ---
    # Default parse mode can be set here or per message. HTML is often useful.
    bot = Bot(token=global_config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)

    # --- Initialize Services ---
    # ConfigManager is mostly module-level functions, but if it were a class:
    # config_service = config_manager.ConfigManager() 
    gsheet_service_instance = GSheetService(credentials_path=str(global_config.GSPREAD_KEY_FILE_PATH))
    llm_service_instance = LLMService()
    user_group_link_service_instance = UserGroupLinkService(
        shelf_file_path=str(global_config.SHELF_FILE_PATH),
        shelf_key=global_config.USER_GROUP_LINKS_SHELF_KEY
    )

    # --- Pass service instances to handlers ---
    # Aiogram 3.x allows passing custom arguments to handlers via dispatcher's context
    # or by including them when registering routers if routers accept them.
    # For simplicity, we can pass them as workflow_data to the dispatcher.
    # These will be available in handlers as keyword arguments.
    dp["gsheet_service_instance"] = gsheet_service_instance
    dp["llm_service_instance"] = llm_service_instance
    dp["user_group_link_service"] = user_group_link_service_instance
    # config_manager functions are directly importable.

    # --- Register Routers/Handlers ---
    # If you have a main aggregated router in handlers/__init__.py:
    # from app.handlers import all_handlers_router
    # dp.include_router(all_handlers_router)
    # Otherwise, register individual routers:
    dp.include_router(admin_router)
    dp.include_router(user_router)
    logger.info("Message and callback handlers registered.")

    # --- Register Middlewares (if any) ---
    # Example: dp.update.outer_middleware(SomeMiddleware())

    # --- Bot Commands Menu (Optional) ---
    # from aiogram.types import BotCommand, BotCommandScopeDefault
    # await bot.set_my_commands([
    #     BotCommand(command="start", description="Start interacting with the bot"),
    #     BotCommand(command="help", description="Get help information"),
    #     # Add admin commands if you want them in the menu for admins
    # ], scope=BotCommandScopeDefault())
    # logger.info("Bot commands menu configured.")


    # --- Graceful Shutdown ---
    # This is a basic example. You might want more sophisticated cleanup.
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

