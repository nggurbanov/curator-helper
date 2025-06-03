# app/handlers/admin.py
"""
Contains Aiogram message handlers and callback query handlers
specifically for administrative commands.
- /setfaqsheet, /setpersonalityprompt, /setwelcomemessage, /addmention,
- /editmentions, /seterror, /toggleanonq, /showsettings, /refresh.
- Admin status checks are performed at the beginning of these handlers.
- Callbacks related to these admin commands are also defined here.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject, StateFilter, CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile, URLInputFile # For sending files if needed
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup # If using FSM for multi-step commands
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import re # Add this import at the top of your file

from app.services import utils, config_manager, gsheet_service, llm_service
from app.keyboards import admin_keyboards
from app import config # For BOSS_ID, etc.

logger = logging.getLogger(__name__)
router = Router(name="admin_handlers")

# --- FSM States (if needed for multi-step operations like /setfaqsheet) ---
class AdminSetSheet(StatesGroup):
    waiting_for_gsheet_url = State()

# Remove or comment out FSM States for commands being changed:
class AdminSetPersonality(StatesGroup):
    waiting_for_prompt_text = State()
    confirming_prompt = State()

class AdminSetWelcome(StatesGroup):
    waiting_for_welcome_text = State()
    confirming_welcome = State()
    
class AdminSetErrorMsg(StatesGroup): # If this existed
    waiting_for_error_text = State()
    confirming_error_msg = State()


# --- Helper Decorator for Admin Check ---
# This is a more advanced way to do it, but for simplicity, we'll do checks inside handlers.
# You could create a custom filter: class AdminFilter(Filter): ...

# --- Helper for MarkdownV2 Escaping ---
def escape_markdown_v2(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2."""
    # Order matters for some escape sequences like '\' itself.
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    # Escape the escape character itself first if it's part of the text
    text = text.replace('\\', '\\\\') 
    # Then escape other special characters
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# --- Admin Command Handlers ---

@router.message(Command("setfaqsheet"), StateFilter(None)) # Ensure not already in a state
async def cmd_set_faq_sheet(message: Message, bot: Bot, state: FSMContext, gsheet_service_instance: gsheet_service.GSheetService):
    if not message.chat.type in ["group", "supergroup"]:
        await message.reply("This command can only be used in group chats.")
        return
    if not await utils.is_chat_admin(bot, message.chat.id, message.from_user.id):
        chat_conf = config_manager.get_chat_config(message.chat.id)
        await message.reply(chat_conf.get("error_message_non_admin", "Sorry, only chat admins can use this command."))
        return

    # Get bot info to construct the deep link
    me = await bot.get_me()
    bot_username = me.username
    
    # Construct the deep link payload: "setfaqsheet_<chat_id>"
    deep_link_payload = f"setfaqsheet_{message.chat.id}"
    start_link = f"https://t.me/{bot_username}?start={deep_link_payload}"

    await message.reply(
        "Okay, let's set up the Google Sheet for FAQs and bot settings for this chat.\n"
        f"Please click the link below to continue in a private message with me:\n"
        f"{start_link}\n\n"
        "Once in the private chat, you'll be prompted to send the Google Sheet URL.\n"
        f"Remember to share the Google Sheet with this email address with 'Editor' permissions: `{config.GSPREAD_SERVICE_ACCOUNT_EMAIL}`."
    )
    # The state will now be set in the PM handler after clicking the deep link.
    logger.info(f"Admin {message.from_user.id} initiated /setfaqsheet for chat {message.chat.id}. Sent deep link to PM.")


# New handler for the deep link in private chat
@router.message(CommandStart(deep_link=True, magic=F.args.regexp(r'setfaqsheet_(-?\d+)')), F.chat.type == "private")
async def process_deep_link_setfaqsheet(message: Message, state: FSMContext, command: CommandObject):
    # Extract the chat_id from the deep link payload (e.g., "setfaqsheet_-12345")
    try:
        group_chat_id_str = command.args.split('_')[1]
        target_chat_id = int(group_chat_id_str)
    except (IndexError, ValueError):
        await message.reply("Invalid link. Please use the link provided in the group chat.")
        await state.clear()
        return

    # Check if the user who clicked the deep link is an admin in the target group chat
    if not await utils.is_chat_admin(message.bot, target_chat_id, message.from_user.id):
        await message.reply("You are not an admin in the specified group chat. Only admins can configure the Google Sheet.")
        await state.clear()
        return

    await state.update_data(target_chat_id=target_chat_id)
    await state.set_state(AdminSetSheet.waiting_for_gsheet_url)
    
    await message.reply(
        f"Hello {message.from_user.first_name}! You've initiated setting the Google Sheet for chat ID: {target_chat_id}.\n"
        "Please send me the full URL of your Google Sheet now.\n"
        f"Remember to share it with `{config.GSPREAD_SERVICE_ACCOUNT_EMAIL}` (Editor role)."
    )
    logger.info(f"User {message.from_user.id} clicked deep link for chat {target_chat_id}. Awaiting GSheet URL in PM.")


@router.message(AdminSetSheet.waiting_for_gsheet_url, F.chat.type == "private")
async def process_gsheet_url_pm(message: Message, state: FSMContext, gsheet_service_instance: gsheet_service.GSheetService, bot: Bot):
    # This handler assumes we can get the target chat_id from state or a previous interaction.
    # For a robust solution, the /setfaqsheet command should store the target chat_id in FSM state.
    # For this example, we'll assume it's implicitly known or needs to be passed.
    # A better way: /setfaqsheet in group stores group_chat_id in FSM state.
    # Then this PM handler uses that stored group_chat_id.

    # Let's assume state contains target_chat_id (needs to be set by the group command handler)
    # For now, this is a simplified placeholder.
    # Stored data in FSM: await state.update_data(target_chat_id=message.chat.id) in the group command.
    fsm_data = await state.get_data()
    target_chat_id = fsm_data.get("target_chat_id") # This needs to be set by the /setfaqsheet group handler

    if not target_chat_id: # Simplified: If not set by /setfaqsheet in group, this won't work well.
        await message.reply("I'm not sure which group chat this Google Sheet URL is for. Please initiate the `/setfaqsheet` command from the group chat first.")
        await state.clear()
        return

    gsheet_url = message.text.strip()
    if not gsheet_url.startswith("https://docs.google.com/spreadsheets/d/"):
        await message.reply("That doesn't look like a valid Google Sheet URL. Please send the full URL.")
        return

    await message.reply(f"Thanks! Checking Google Sheet: {gsheet_url} for chat ID {target_chat_id}...")

    access_ok, error_msg =  gsheet_service_instance.check_spreadsheet_access(gsheet_url)
    if not access_ok:
        await message.reply(f"Failed to access the Google Sheet: {error_msg}\nPlease double-check the URL and sharing permissions with `{config.GSPREAD_SERVICE_ACCOUNT_EMAIL}` (Editor role).")
        await state.clear()
        return

    # Try to read a few FAQs as a sample
    chat_config_defaults = config_manager.get_default_settings()
    faq_sheet_name = chat_config_defaults.get("faq_sheet_name", "FAQs") # Get default name
    settings_sheet_name = chat_config_defaults.get("settings_sheet_name", "BotSettings")

    faqs_list = gsheet_service_instance.read_faqs(gsheet_url, faq_sheet_name)
    faq_count = 0
    if faqs_list is None:
        await message.reply(f"Could not read FAQs from the sheet named \'{faq_sheet_name}\'. It might be missing, empty, or I don\'t have permission. Please ensure it exists and is shared. FAQs will not be available until resolved and refreshed.")
        # Store an empty list or None to indicate no FAQs are currently loaded
        config_manager.set_chat_setting(target_chat_id, "faqs_list", []) 
        faq_sample_text = "Warning: FAQ sheet could not be read. No FAQs loaded locally."
    elif not faqs_list:
        config_manager.set_chat_setting(target_chat_id, "faqs_list", [])
        faq_sample_text = f"The FAQ sheet \'{faq_sheet_name}\' appears to be empty. No FAQs loaded locally. That\'s okay, you can add FAQs later to the sheet and then use /refresh."
    else:
        faq_count = len(faqs_list)
        config_manager.set_chat_setting(target_chat_id, "faqs_list", faqs_list)
        faq_sample_text = f"Found and stored {faq_count} FAQs locally. Here are the first few (up to 3):\\n"
        for i, (q, a) in enumerate(faqs_list[:3]):
            faq_sample_text += f"{i+1}. Q: {q[:50]}... A: {a[:50]}...\\n"
    
    await message.reply(faq_sample_text)

    # Attempt to write/ensure the BotSettings sheet
    # Get current full config for the chat, which will be defaults if new
    current_chat_settings = config_manager.get_chat_config(target_chat_id) 
    current_chat_settings["gsheet_url"] = gsheet_url # Update the URL

    if gsheet_service_instance.write_settings_sheet(gsheet_url, settings_sheet_name, current_chat_settings, chat_config_defaults):
        await message.reply(f"The \'BotSettings\' sheet (\'{settings_sheet_name}\') has been prepared in your Google Sheet.")
        # Save to shelve
        current_chat_settings["gsheet_sync_conflict"] = False # Fresh setup, no conflict
        # We already updated faqs_list above, ensure current_chat_settings reflects that before full update if necessary
        # However, config_manager.set_chat_setting for "faqs_list" already saved it.
        # update_chat_config will save other settings along with the gsheet_url and conflict flag.
        if config_manager.update_chat_config(target_chat_id, current_chat_settings): # This saves the gsheet_url and other settings
            await message.reply(f"Successfully configured Google Sheet for chat ID {target_chat_id}! Settings and {faq_count} FAQs (if any) are now stored locally.")
            logger.info(f"GSheet URL {gsheet_url} configured for chat {target_chat_id} by admin {message.from_user.id}. {faq_count} FAQs stored locally.")
            # Also inform in the group chat
            try:
                await bot.send_message(target_chat_id, f"Admin {message.from_user.full_name} has successfully configured the Google Sheet for our FAQs and settings!")
            except Exception as e:
                logger.error(f"Could not send confirmation to group chat {target_chat_id}: {e}")
        else:
            await message.reply("Error: Could not save the configuration internally. Please try again or contact the bot owner.")
    else:
        await message.reply(f"Error: Could not write to the \'BotSettings\' sheet (\'{settings_sheet_name}\'). Please check permissions. Configuration not saved.")
        # Potentially set sync conflict flag here if shelve was updated before this check
        config_manager.set_chat_setting(target_chat_id, "gsheet_sync_conflict", True)

    await state.clear()


@router.message(Command("seterror"))
async def cmd_set_error_message(
    message: Message,
    bot: Bot,
    command: CommandObject,
    gsheet_service_instance: gsheet_service.GSheetService
):
    if not message.chat.type in ["group", "supergroup"]:
        await message.reply("This command can only be used in group chats.")
        return
    if not await utils.is_chat_admin(bot, message.chat.id, message.from_user.id):
        chat_conf = config_manager.get_chat_config(message.chat.id)
        await message.reply(chat_conf.get("error_message_non_admin", "Only admins can set the error message."))
        return

    chat_id = message.chat.id
    error_text = command.args

    if not error_text:
        await message.reply(
            "Please provide the error message text after the command.\n"
            "Usage: `/seterror Your new error message`"
        )
        return

    if len(error_text.strip()) < 10: # Arbitrary minimum length
        await message.reply("The error message seems too short. Please provide a more descriptive message.")
        return
    
    error_text = error_text.strip()
    # Assuming the setting key in config_manager is 'bot_generic_error_message'
    # Adjust this key if it's different in your config_manager.
    setting_key = "bot_generic_error_message" 
    config_manager.set_chat_setting(chat_id, setting_key, error_text)
    
    chat_conf_updated = config_manager.get_chat_config(chat_id)
    default_settings_schema = config_manager.get_default_settings()
    gsheet_url = chat_conf_updated.get("gsheet_url")
    settings_sheet_name = chat_conf_updated.get("settings_sheet_name", "BotSettings")

    gsheet_update_success = False
    gsheet_sync_attempted = False
    if gsheet_url and settings_sheet_name:
        gsheet_sync_attempted = True
        if gsheet_service_instance.write_settings_sheet(
            gsheet_url,
            settings_sheet_name,
            chat_conf_updated,
            default_settings_schema
        ):
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", False)
            gsheet_update_success = True
        else:
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
    elif gsheet_url: # URL exists but sheet name might be missing
        gsheet_sync_attempted = True # Still consider it an attempt if partial config exists
        config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
        logger.warning(f"GSheet settings sheet name not configured for chat {chat_id} but URL exists. Error message set locally only, conflict flagged.")
    else:
        logger.info(f"GSheet URL not configured for chat {chat_id}. Error message set locally only.")


    if gsheet_update_success:
        await message.reply(f"Default error message has been updated successfully and synced to Google Sheet:\n```\n{error_text}\n```")
    elif gsheet_sync_attempted: # Attempted GSheet sync but failed
        await message.reply(f"Default error message has been updated locally, but **failed to sync to Google Sheet**. A conflict is flagged.\nNew message:\n```\n{error_text}\n```")
    else: # GSheet not configured for sync (no URL)
        await message.reply(f"Default error message has been updated locally. Google Sheet not configured for settings sync.\nNew message:\n```\n{error_text}\n```")
        
    logger.info(f"Admin {message.from_user.id} set error message for chat {chat_id}: '{error_text[:50]}...'")


@router.message(Command("setpersonalityprompt"))
async def cmd_set_personality_prompt(
    message: Message,
    bot: Bot,
    command: CommandObject,
    gsheet_service_instance: gsheet_service.GSheetService
):
    if not message.chat.type in ["group", "supergroup"]:
        await message.reply("This command can only be used in group chats.")
        return
    if not await utils.is_chat_admin(bot, message.chat.id, message.from_user.id):
        chat_conf = config_manager.get_chat_config(message.chat.id)
        await message.reply(chat_conf.get("error_message_non_admin", "Only admins can set the personality prompt."))
        return

    chat_id = message.chat.id
    prompt_text = command.args

    if not prompt_text:
        await message.reply(
            "Please provide the personality prompt text after the command.\n"
            "Usage: `/setpersonalityprompt Your new prompt text`"
        )
        return

    if len(prompt_text.strip()) < 20: # Arbitrary min length
        await message.reply("The personality prompt seems too short. Please provide a more descriptive prompt.")
        return

    prompt_text = prompt_text.strip()
    setting_key = "personality_prompt_text"
    config_manager.set_chat_setting(chat_id, setting_key, prompt_text)
    
    chat_conf_updated = config_manager.get_chat_config(chat_id)
    default_settings_schema = config_manager.get_default_settings()
    gsheet_url = chat_conf_updated.get("gsheet_url")
    settings_sheet_name = chat_conf_updated.get("settings_sheet_name", "BotSettings")

    gsheet_update_success = False
    gsheet_sync_attempted = False
    if gsheet_url and settings_sheet_name:
        gsheet_sync_attempted = True
        if gsheet_service_instance.write_settings_sheet(
            gsheet_url,
            settings_sheet_name,
            chat_conf_updated,
            default_settings_schema
        ):
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", False)
            gsheet_update_success = True
        else:
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
    elif gsheet_url:
        gsheet_sync_attempted = True
        config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
        logger.warning(f"GSheet settings sheet name not configured for chat {chat_id} but URL exists. Personality prompt set locally only, conflict flagged.")
    else:
        logger.info(f"GSheet URL not configured for chat {chat_id}. Personality prompt set locally only.")

    response_message_intro = "Personality prompt has been updated"
    preview_text = f"{prompt_text[:200]}..." if len(prompt_text) > 200 else prompt_text

    if gsheet_update_success:
        await message.reply(f"{response_message_intro} successfully and synced to Google Sheet.\nPreview:\n```\n{preview_text}\n```")
    elif gsheet_sync_attempted:
        await message.reply(f"{response_message_intro} locally, but **failed to sync to Google Sheet**. A conflict is flagged.\nPreview:\n```\n{preview_text}\n```")
    else:
        await message.reply(f"{response_message_intro} locally. Google Sheet not configured for settings sync.\nPreview:\n```\n{preview_text}\n```")
        
    logger.info(f"Admin {message.from_user.id} set personality prompt for chat {chat_id}: '{prompt_text[:50]}...'")


@router.message(Command("showsettings"))
async def cmd_show_settings(message: Message, bot: Bot):
    if not message.chat.type in ["group", "supergroup"]:
        await message.reply("This command can only be used in group chats to show its settings.")
        return

    chat_id = message.chat.id # Get chat_id for config
    chat_conf = config_manager.get_chat_config(chat_id) # Use chat_id
    
    if not chat_conf: # Check if chat_conf is None or empty
        await message.reply("No settings found for this chat.")
        return

    settings_text = "Current Bot Settings for this Chat:\n\n"
    for key, value in chat_conf.items():
        escaped_key = escape_markdown_v2(str(key))
        # Truncate before escaping to avoid escaping already truncated part.
        # Or escape then truncate, but be mindful of half-escaped sequences at the end.
        # For simplicity, truncate then escape.
        value_str = str(value)
        truncated_value = value_str[:150] # Shorten truncation a bit more to be safe with escaped chars
        if len(value_str) > 150:
            truncated_value += "..."
            
        escaped_value = escape_markdown_v2(truncated_value)
        
        # Using a hyphen for a list item requires careful spacing or escaping the hyphen itself
        # if it's not at the start of a proper list.
        # Let's escape the leading hyphen to be safe, or use a different bullet point.
        # For this example, we'll escape it.
        settings_text += f"\\- `{escaped_key}`: `{escaped_value}`\n"
    
    if settings_text == "Current Bot Settings for this Chat:\n\n": # No settings were added
        await message.reply("No settings configured or available to display for this chat.")
        return

    try:
        await message.reply(settings_text, parse_mode="MarkdownV2")
    except Exception as e: # Catch potential errors during sending
        logger.error(f"Error sending /showsettings message with MarkdownV2: {e}")
        # Fallback to sending without parse_mode or with HTML if preferred
        fallback_text = "Current Bot Settings for this Chat (plain text):\n\n"
        for key, value in chat_conf.items():
            fallback_text += f"- {key}: {str(value)[:200]}\n"
        await message.reply(fallback_text)


@router.message(Command("refresh"))
async def cmd_refresh(message: Message, bot: Bot, 
                      gsheet_service_instance: gsheet_service.GSheetService, 
                      llm_service_instance: llm_service.LLMService # If FAQs need to be processed/enumerated by LLMService
                     ):
    if not message.chat.type in ["group", "supergroup"]:
        await message.reply("This command can only be used in group chats.")
        return
    if not await utils.is_chat_admin(bot, message.chat.id, message.from_user.id):
        chat_conf_for_error = config_manager.get_chat_config(message.chat.id)
        await message.reply(chat_conf_for_error.get("error_message_non_admin", "Only admins can refresh settings."))
        return

    chat_id = message.chat.id
    await message.reply("Refreshing FAQs and settings from Google Sheet... This might take a moment.")

    chat_conf = config_manager.get_chat_config(chat_id)
    gsheet_url = chat_conf.get("gsheet_url")

    if not gsheet_url:
        await message.reply("Google Sheet URL is not configured for this chat. Please use `/setfaqsheet` first.")
        return

    faq_refresh_ok = False
    settings_refresh_ok = False
    faq_count = 0

    # 1. Refresh FAQs
    faq_sheet_name = chat_conf.get("faq_sheet_name", config_manager.get_default_settings().get("faq_sheet_name", "FAQs"))
    try:
        faqs_list = gsheet_service_instance.read_faqs(gsheet_url, faq_sheet_name)
        if faqs_list is not None:
            if config_manager.set_chat_setting(chat_id, "faqs_list", faqs_list):
                faq_count = len(faqs_list)
                faq_refresh_ok = True
                logger.info(f"Successfully refreshed and stored {faq_count} FAQs for chat {chat_id} from GSheet.")
            else:
                logger.error(f"Failed to save refreshed FAQs to shelve for chat {chat_id}.")
        else:
            # read_faqs returned None, indicating an error reading the sheet (e.g. not found, permissions)
            # Store empty list in shelve to clear any stale FAQs
            config_manager.set_chat_setting(chat_id, "faqs_list", [])
            logger.warning(f"Could not read FAQs from GSheet for chat {chat_id} during refresh. Sheet might be missing or inaccessible. Local FAQs cleared.")
            # faq_refresh_ok remains False
            
    except Exception as e:
        config_manager.set_chat_setting(chat_id, "faqs_list", []) # Clear local FAQs on error
        logger.error(f"Exception during FAQ refresh for chat {chat_id}: {e}", exc_info=True)
        # faq_refresh_ok remains False

    # 2. Refresh Settings
    settings_sheet_name = chat_conf.get("settings_sheet_name", config_manager.get_default_settings().get("settings_sheet_name", "BotSettings"))
    try:
        gsheet_settings = gsheet_service_instance.read_settings_sheet(gsheet_url, settings_sheet_name)
    except Exception as e:
        logger.error(f"Exception reading settings from GSheet for chat {chat_id}: {e}", exc_info=True)
        gsheet_settings = None

    if gsheet_settings is not None:
        # Merge with existing config to preserve any keys not in GSheet (though ideally all are)
        # GSheet settings take precedence.
        # current local config already in chat_conf. We need to preserve "faqs_list" we just updated.
        refreshed_faqs = config_manager.get_chat_config(chat_id).get("faqs_list", []) # Re-get updated faqs_list

        new_chat_conf = chat_conf.copy() # Start with current shelve (which includes old settings and potentially old faqs_list)
        new_chat_conf.update(gsheet_settings) # Override with GSheet values
        new_chat_conf["gsheet_sync_conflict"] = False # Sync was successful for settings part
        new_chat_conf["faqs_list"] = refreshed_faqs # Ensure the just-refreshed FAQs are part of this update.
        
        if config_manager.update_chat_config(chat_id, new_chat_conf):
            logger.info(f"Settings refreshed from GSheet and updated in shelve for chat {chat_id}.")
            settings_refresh_ok = True
        else:
            logger.error(f"Failed to save GSheet settings to shelve for chat {chat_id}.")
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True) # Mark conflict
    else:
        logger.error(f"Failed to read settings from GSheet for chat {chat_id}. Marking settings conflict.")
        config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)

    # 3. Provide Feedback
    if faq_refresh_ok and settings_refresh_ok:
        await message.reply(f"Refresh complete! Loaded and stored {faq_count} FAQs locally. Bot settings also updated from the Google Sheet.")
    elif faq_refresh_ok:
        await message.reply(f"Loaded and stored {faq_count} FAQs locally. However, there was an error refreshing bot settings from the Google Sheet. A settings sync conflict has been flagged.")
    elif settings_refresh_ok:
        await message.reply("Bot settings updated from Google Sheet and stored locally. However, there was an error reading/storing FAQs. Local FAQs might be empty or outdated. Please check your Google Sheet and bot logs.")
    else:
        await message.reply("Refresh failed. Errors occurred while reading/storing both FAQs and settings. Local FAQs might be empty or outdated, and a settings sync conflict has been flagged. Please check your Google Sheet and bot logs.")


@router.message(Command("setwelcomemessage"))
async def cmd_set_welcome_message(
    message: Message,
    bot: Bot,
    command: CommandObject,
    gsheet_service_instance: gsheet_service.GSheetService
):
    if not message.chat.type in ["group", "supergroup"]:
        await message.reply("This command can only be used in group chats.")
        return
    if not await utils.is_chat_admin(bot, message.chat.id, message.from_user.id):
        chat_conf = config_manager.get_chat_config(message.chat.id)
        await message.reply(chat_conf.get("error_message_non_admin", "Only admins can set the welcome message."))
        return

    chat_id = message.chat.id
    welcome_text = command.args

    if not welcome_text:
        await message.reply(
            "Please provide the welcome message text after the command.\n"
            "Usage: `/setwelcomemessage Your new welcome message`"
        )
        return

    if len(welcome_text.strip()) < 10: # Arbitrary minimum length
        await message.reply("The welcome message seems too short. Please provide a more descriptive message.")
        return
    
    welcome_text = welcome_text.strip()
    setting_key = "welcome_message" 
    config_manager.set_chat_setting(chat_id, setting_key, welcome_text)
    
    chat_conf_updated = config_manager.get_chat_config(chat_id)
    default_settings_schema = config_manager.get_default_settings()
    gsheet_url = chat_conf_updated.get("gsheet_url")
    settings_sheet_name = chat_conf_updated.get("settings_sheet_name", "BotSettings")

    gsheet_update_success = False
    gsheet_sync_attempted = False
    if gsheet_url and settings_sheet_name:
        gsheet_sync_attempted = True
        if gsheet_service_instance.write_settings_sheet(
            gsheet_url, settings_sheet_name, chat_conf_updated, default_settings_schema
        ):
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", False)
            gsheet_update_success = True
        else:
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
    elif gsheet_url:
        gsheet_sync_attempted = True
        config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
        logger.warning(f"GSheet settings sheet name not configured for chat {chat_id} but URL exists. Welcome message set locally only, conflict flagged.")
    else:
        logger.info(f"GSheet URL not configured for chat {chat_id}. Welcome message set locally only.")

    preview_text = f"{welcome_text[:200]}..." if len(welcome_text) > 200 else welcome_text
    if gsheet_update_success:
        await message.reply(f"Welcome message has been updated successfully and synced to Google Sheet.\nPreview:\n```\n{preview_text}\n```")
    elif gsheet_sync_attempted:
        await message.reply(f"Welcome message has been updated locally, but **failed to sync to Google Sheet**. A conflict is flagged.\nPreview:\n```\n{preview_text}\n```")
    else:
        await message.reply(f"Welcome message has been updated locally. Google Sheet not configured for settings sync.\nPreview:\n```\n{preview_text}\n```")
        
    logger.info(f"Admin {message.from_user.id} set welcome message for chat {chat_id}: '{welcome_text[:50]}...'")


@router.message(Command("toggleanonq"))
async def cmd_toggle_anon_q(
    message: Message,
    bot: Bot,
    gsheet_service_instance: gsheet_service.GSheetService
):
    if not message.chat.type in ["group", "supergroup"]:
        await message.reply("This command can only be used in group chats.")
        return
    if not await utils.is_chat_admin(bot, message.chat.id, message.from_user.id):
        chat_conf = config_manager.get_chat_config(message.chat.id)
        await message.reply(chat_conf.get("error_message_non_admin", "Only admins can toggle this setting."))
        return

    chat_id = message.chat.id
    setting_key = "allow_anonymous_questions" # Ensure this key exists in your default_settings
    
    current_chat_conf = config_manager.get_chat_config(chat_id)
    current_value = current_chat_conf.get(setting_key, False) # Default to False if not set
    new_value = not current_value

    config_manager.set_chat_setting(chat_id, setting_key, new_value)
    
    chat_conf_updated = config_manager.get_chat_config(chat_id) # Re-fetch after update
    default_settings_schema = config_manager.get_default_settings()
    gsheet_url = chat_conf_updated.get("gsheet_url")
    settings_sheet_name = chat_conf_updated.get("settings_sheet_name", "BotSettings")

    gsheet_update_success = False
    gsheet_sync_attempted = False
    if gsheet_url and settings_sheet_name:
        gsheet_sync_attempted = True
        if gsheet_service_instance.write_settings_sheet(
            gsheet_url, settings_sheet_name, chat_conf_updated, default_settings_schema
        ):
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", False)
            gsheet_update_success = True
        else:
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
    elif gsheet_url:
        gsheet_sync_attempted = True
        config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
    
    status_text = "enabled" if new_value else "disabled"
    reply_message_text = f"Anonymous questions are now **{status_text}** for this chat."

    if gsheet_update_success:
        reply_message_text += "\nSetting synced to Google Sheet."
    elif gsheet_sync_attempted:
        reply_message_text += "\nSetting updated locally, but **failed to sync to Google Sheet**. Conflict flagged."
    else:
        reply_message_text += "\nGoogle Sheet not configured for settings sync."
        
    await message.reply(reply_message_text, parse_mode="Markdown")
    logger.info(f"Admin {message.from_user.id} toggled {setting_key} to {new_value} for chat {chat_id}.")


@router.message(Command("addmention"))
async def cmd_add_mention(
    message: Message,
    bot: Bot,
    command: CommandObject,
    gsheet_service_instance: gsheet_service.GSheetService
):
    if not message.chat.type in ["group", "supergroup"]:
        await message.reply("This command can only be used in group chats.")
        return
    if not await utils.is_chat_admin(bot, message.chat.id, message.from_user.id):
        chat_conf = config_manager.get_chat_config(message.chat.id)
        await message.reply(chat_conf.get("error_message_non_admin", "Only admins can add mentions."))
        return

    chat_id = message.chat.id
    args_text = command.args

    if not args_text:
        await message.reply(
            "Please provide the mention keyword and optional description.\n"
            "Usage: `/addmention keyword (optional description)`\n"
            "Example: `/addmention urgent Support Team Lead`"
        )
        return

    parts = args_text.split(maxsplit=1)
    keyword_mention = parts[0]
    description = parts[1] if len(parts) > 1 else ""

    if not keyword_mention or len(keyword_mention) < 2: # Ensure keyword is not empty and has some length
        await message.reply("The mention keyword must be at least 2 characters long.")
        return

    setting_key = "group_mentions" 
    current_chat_conf = config_manager.get_chat_config(chat_id)
    mentions_list = current_chat_conf.get(setting_key, [])

    if any(m['username'].lower() == keyword_mention.lower() for m in mentions_list): # 'username' key still used internally for consistency
        await message.reply(f"The mention keyword `{keyword_mention}` already exists.")
        return

    mentions_list.append({"username": keyword_mention, "description": description.strip()}) # Storing as 'username' internally
    config_manager.set_chat_setting(chat_id, setting_key, mentions_list) 

    chat_conf_updated = config_manager.get_chat_config(chat_id) 
    default_settings_schema = config_manager.get_default_settings()
    gsheet_url = chat_conf_updated.get("gsheet_url")
    settings_sheet_name = chat_conf_updated.get("settings_sheet_name", "BotSettings")

    gsheet_update_success = False
    gsheet_sync_attempted = False
    if gsheet_url and settings_sheet_name:
        gsheet_sync_attempted = True
        if gsheet_service_instance.write_settings_sheet(
            gsheet_url, settings_sheet_name, chat_conf_updated, default_settings_schema
        ):
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", False)
            gsheet_update_success = True
        else:
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
    elif gsheet_url:
        gsheet_sync_attempted = True
        config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)

    reply_message_text = f"Mention keyword `{keyword_mention}` added successfully."
    if description:
        reply_message_text += f" Description: \"{description}\""
    
    if gsheet_update_success:
        reply_message_text += "\nSettings synced to Google Sheet."
    elif gsheet_sync_attempted:
        reply_message_text += "\nSettings updated locally, but **failed to sync to Google Sheet**. Conflict flagged."
    else:
        reply_message_text += "\nGoogle Sheet not configured for settings sync."

    await message.reply(reply_message_text, parse_mode="Markdown")
    logger.info(f"Admin {message.from_user.id} added mention keyword '{keyword_mention}' for chat {chat_id}.")


@router.message(Command("editmentions"))
async def cmd_edit_mentions(message: Message, bot: Bot):
    if not message.chat.type in ["group", "supergroup"]:
        await message.reply("This command can only be used in group chats.")
        return
    if not await utils.is_chat_admin(bot, message.chat.id, message.from_user.id):
        chat_conf = config_manager.get_chat_config(message.chat.id)
        await message.reply(chat_conf.get("error_message_non_admin", "Only admins can edit mentions."))
        return

    chat_id = message.chat.id
    chat_conf = config_manager.get_chat_config(chat_id)
    mentions_list = chat_conf.get("group_mentions", [])

    if not mentions_list:
        await message.reply("There are no mentions configured for this chat. Use `/addmention` to add some.")
        return

    # Make sure your admin_keyboards.py has get_edit_mentions_keyboard and CALLBACK_ADMIN_DELETE_MENTION
    # CALLBACK_ADMIN_DELETE_MENTION = "admin_del_mention"
    keyboard = admin_keyboards.get_edit_mentions_keyboard(chat_id, mentions_list)
    await message.reply("Select a mention to delete:", reply_markup=keyboard)


# --- Callback Query Handlers for Admin Actions ---

@router.callback_query(F.data.startswith(admin_keyboards.CALLBACK_ADMIN_DELETE_MENTION)) # Make sure this constant is defined in admin_keyboards.py
async def handle_delete_mention_callback(
    query: CallbackQuery,
    bot: Bot,
    gsheet_service_instance: gsheet_service.GSheetService
):
    # Data format: "admin_del_mention:chat_id:mention_username_or_index"
    # For simplicity, let's assume username is unique and used.
    # If using index, ensure keyboard sends index and list remains stable or is re-fetched.
    try:
        _, chat_id_str, mention_to_delete_username = query.data.split(":", 2)
        chat_id = int(chat_id_str)
    except ValueError:
        await query.answer("Invalid callback data.", show_alert=True)
        logger.error(f"Invalid callback data for delete mention: {query.data}")
        return

    if not await utils.is_chat_admin(bot, chat_id, query.from_user.id):
        await query.answer("Only admins can perform this action.", show_alert=True)
        return
    
    await query.answer(f"Deleting {mention_to_delete_username}...")

    setting_key = "group_mentions"
    current_chat_conf = config_manager.get_chat_config(chat_id)
    mentions_list = current_chat_conf.get(setting_key, [])
    
    original_len = len(mentions_list)
    # Filter out the mention to delete (case-insensitive username match for robustness)
    mentions_list = [m for m in mentions_list if m['username'].lower() != mention_to_delete_username.lower()]

    if len(mentions_list) == original_len:
        await query.message.edit_text(f"Mention `{mention_to_delete_username}` not found or already deleted. Current list refreshed.",
                                      reply_markup=admin_keyboards.get_edit_mentions_keyboard(chat_id, mentions_list) if mentions_list else None)
        return

    config_manager.set_chat_setting(chat_id, setting_key, mentions_list)

    chat_conf_updated = config_manager.get_chat_config(chat_id) # Re-fetch
    default_settings_schema = config_manager.get_default_settings()
    gsheet_url = chat_conf_updated.get("gsheet_url")
    settings_sheet_name = chat_conf_updated.get("settings_sheet_name", "BotSettings")

    gsheet_update_success = False
    gsheet_sync_attempted = False
    if gsheet_url and settings_sheet_name:
        gsheet_sync_attempted = True
        if gsheet_service_instance.write_settings_sheet(
            gsheet_url, settings_sheet_name, chat_conf_updated, default_settings_schema
        ):
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", False)
            gsheet_update_success = True
        else:
            config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
    elif gsheet_url:
        gsheet_sync_attempted = True
        config_manager.set_chat_setting(chat_id, "gsheet_sync_conflict", True)

    response_message_text = f"Mention `{mention_to_delete_username}` deleted."
    if gsheet_update_success:
        response_message_text += " Synced to GSheet."
    elif gsheet_sync_attempted:
        response_message_text += " Synced locally, GSheet sync failed. Conflict flagged."
    else:
        response_message_text += " Synced locally. GSheet not configured."

    if mentions_list:
        await query.message.edit_text(response_message_text + "\nUpdated list of mentions:",
                                      reply_markup=admin_keyboards.get_edit_mentions_keyboard(chat_id, mentions_list))
    else:
        await query.message.edit_text(response_message_text + "\nNo mentions remaining.")
    
    logger.info(f"Admin {query.from_user.id} deleted mention '{mention_to_delete_username}' for chat {chat_id}.")


# ... (handle_confirm_setting_callback - review if it's still needed for any other command, or simplify/remove parts)
# ... (handle_cancel_setting_callback - review if still needed)
# ... (handle_conflict_push_callback, handle_conflict_pull_callback remain useful)

# Ensure the placeholder comment is updated or removed
# logger.info("Admin command and callback handlers registered.")

# Conceptual helper - will be integrated into the command handlers below
async def _update_setting_and_gsheet(
    chat_id: int,
    setting_key: str,
    new_value: any,
    config_manager_instance: config_manager, # Assuming you pass instances or access them
    gsheet_service_instance: gsheet_service.GSheetService,
    logger_instance: logging.Logger
) -> tuple[bool, bool, dict]: # Returns (local_success, gsheet_sync_success, updated_chat_config)
    """
    Updates a setting in config_manager, attempts to sync all settings to GSheet,
    and handles conflict flags.
    Returns:
        - local_update_success (bool)
        - gsheet_sync_success (bool) - True if synced, False if failed or not attempted
        - gsheet_sync_attempted (bool)
        - updated_chat_config (dict)
    """
    local_update_success = config_manager_instance.set_chat_setting(chat_id, setting_key, new_value)
    if not local_update_success: # Should ideally not happen if key is valid
        logger_instance.error(f"Failed to set setting '{setting_key}' locally for chat {chat_id}.")
        # Still try to fetch current config for GSheet sync if needed, or return early
        # For simplicity, assume local_update_success is true if set_chat_setting doesn't raise error
        # or if it implies success by not returning False explicitly.
        # config_manager.set_chat_setting might return None or be void.
        # Let's assume it works and proceed.
        pass # Or handle more robustly

    updated_chat_config = config_manager_instance.get_chat_config(chat_id)
    # If the specific setting was part of a larger dict (e.g. list of mentions),
    # new_value would be the whole updated dict/list.
    # For simple key-value, updated_chat_config will now reflect the change.

    gsheet_url = updated_chat_config.get("gsheet_url")
    settings_sheet_name = updated_chat_config.get("settings_sheet_name", "BotSettings")
    default_settings_schema = config_manager_instance.get_default_settings()

    gsheet_sync_success = False
    gsheet_sync_attempted = False

    if gsheet_url and settings_sheet_name:
        gsheet_sync_attempted = True
        if await gsheet_service_instance.write_settings_sheet( # Assuming gsheet service methods are async now
            gsheet_url,
            settings_sheet_name,
            updated_chat_config, # Send the whole config
            default_settings_schema
        ):
            config_manager_instance.set_chat_setting(chat_id, "gsheet_sync_conflict", False)
            gsheet_sync_success = True
        else:
            config_manager_instance.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
            logger_instance.error(f"Failed to write settings to GSheet for chat {chat_id} after updating '{setting_key}'.")
    elif gsheet_url: # URL exists but sheet name might be missing
        gsheet_sync_attempted = True
        config_manager_instance.set_chat_setting(chat_id, "gsheet_sync_conflict", True)
        logger_instance.warning(f"GSheet settings_sheet_name not configured for chat {chat_id} but URL exists. Setting '{setting_key}' updated locally, GSheet conflict flagged.")
    else:
        logger_instance.info(f"GSheet not configured for chat {chat_id}. Setting '{setting_key}' updated locally only.")

    return True, gsheet_sync_success, gsheet_sync_attempted, updated_chat_config
