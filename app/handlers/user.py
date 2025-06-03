# app/handlers/user.py
"""
Contains Aiogram message handlers and callback query handlers for general user interactions.
- /start, /help commands.
- Handling regular text messages for FAQ lookups or general chat.
- Chat member join events (custom welcome message).
- Callbacks related to general user interactions (e.g., "OK" / "ASK" buttons).
"""
import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER, CommandObject
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Text, Bold, Italic, ExpandableBlockQuote
from aiogram.enums import ChatType

from app.services import utils, config_manager, gsheet_service, llm_service
from app.services.user_group_link_service import UserGroupLinkService
from app.keyboards import inline_keyboards
from app import config as global_config

logger = logging.getLogger(__name__)
router = Router(name="user_handlers")

# --- User Command Handlers ---

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    chat_conf = config_manager.get_chat_config(message.chat.id)
    bot_name = chat_conf.get("bot_display_name", "Helper Bot")
    await message.answer(
        f"Hello, {message.from_user.first_name}! I'm {bot_name}.\n"
        "I can help answer questions based on our program's FAQ.\n"
        "If I'm in a group chat, you can usually trigger me by mentioning my name or keywords.\n"
        "Type /help for more information if available."
    )

@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot):
    await message.answer(
        "This bot helps answer Frequently Asked Questions for this program.\n"
        "In group chats, I respond when mentioned by my configured keywords.\n"
        "Available admin commands (usable by chat admins in groups):\n"
        "- `/setfaqsheet`: Configure the Google Sheet for FAQs and settings.\n"
        "- `/setpersonalityprompt {prompt}`: Set my chat personality for non-FAQ responses.\n"
        "- `/setwelcomemessage {message}`: Customize the welcome message for new users.\n"
        "- `/addmention {keyword}`: Add a keyword I should respond to.\n"
        "- `/editmentions`: View and delete configured mentions.\n"
        "- `/seterror {message}`: Set the error message for non-admin command use.\n"
        "- `/toggleanonq`: Enable/disable anonymous questions to curators.\n"
        "- `/showsettings`: Display my current settings for this chat.\n"
        "- `/refresh`: Reload FAQs and settings from the Google Sheet."
    )

# --- Chat Member Update Handler (Welcome Message) ---
@router.chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER)) # User joins the chat
async def on_user_joined(event: ChatMemberUpdated, bot: Bot):
    chat_conf = config_manager.get_chat_config(event.chat.id)
    welcome_template = chat_conf.get("welcome_message", "Welcome, {username}!")
    
    # Replace placeholders. {username} is common. {user_mention_html} for a clickable one.
    user_html_mention = utils.get_user_mention_html(event.new_chat_member.user.id, event.new_chat_member.user.first_name)
    
    # A more robust placeholder system might be needed for more complex templates
    # For now, simple replace:
    welcome_message = welcome_template.replace("{username}", event.new_chat_member.user.first_name)
    welcome_message = welcome_message.replace("{user_mention}", f"@{event.new_chat_member.user.username}" if event.new_chat_member.user.username else event.new_chat_member.user.first_name)
    welcome_message = welcome_message.replace("{user_mention_html}", user_html_mention)
    welcome_message = welcome_message.replace("{chat_title}", event.chat.title or "the chat")

    try:
        await bot.send_message(event.chat.id, welcome_message, parse_mode="HTML")
        logger.info(f"Sent welcome message to {event.new_chat_member.user.id} in chat {event.chat.id}")
    except Exception as e:
        logger.error(f"Failed to send welcome message in chat {event.chat.id}: {e}")


# --- User Group Linking and Anonymous Questions (PM Handlers) ---

@router.message(F.chat.type == ChatType.PRIVATE, F.forward_from_chat)
async def handle_forwarded_group_message(message: Message, user_group_link_service: UserGroupLinkService):
    logger.critical("CRITICAL_DEBUG: Entered handle_forwarded_group_message!")
    logger.info(f"DEBUG_FORWARD: message.chat.type = {message.chat.type}")
    logger.info(f"DEBUG_FORWARD: message.forward_from_chat = {message.forward_from_chat}")
    """
    Handles a forwarded message in a PM to link the user to the origin group chat
    for sending anonymous questions. Validates the group against configured chats.
    """
    user_id = message.from_user.id
    forwarded_chat = message.forward_from_chat

    if not forwarded_chat:
        await message.reply("Could not determine the group from the forwarded message. Please try again.")
        return

    if forwarded_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.reply("You can only link group chats for anonymous questions, not channels or private chats.")
        return

    group_id = forwarded_chat.id
    group_title = forwarded_chat.title or "the group"

    # --- Group Validation ---
    # Check if this group_id is known/configured in chat_configs.shelf.db
    # We can try to get its config. If it doesn't exist, config_manager usually returns default or raises error.
    # A more direct way is to check if its ID is in the list of all known chat IDs.
    known_chat_ids = config_manager.get_all_chat_ids() # Assumes this function exists in config_manager
    if group_id not in known_chat_ids:
        logger.warning(f"User {user_id} attempted to link to unconfigured group {group_id} ('{group_title}').")
        await message.reply(
            f"Sorry, I am not actively configured for the group **'{group_title}'**. "
            "Please forward a message from a group where I have been set up by an admin."
        )
        return
    # --- End Group Validation ---

    if user_group_link_service.set_user_group_link(user_id, group_id):
        logger.info(f"User {user_id} successfully linked to configured group {group_id} ('{group_title}') for anonymous questions.")
        await message.reply(
            f"Great! I've linked you to the group **'{group_title}'**. "
            f"You can now send anonymous questions to this group using the `/anon &lt;your question&gt;` command in our PM."
        )
    else:
        logger.error(f"Failed to save link for user {user_id} to group {group_id}.")
        await message.reply("Sorry, there was an issue saving this link. Please try again later.")


# --- Regular Message Handler (FAQ Lookup & General Chat) ---
@router.message(F.text)
async def handle_text_message(
    message: Message, 
    bot: Bot, 
    state: FSMContext, 
    gsheet_service_instance: gsheet_service.GSheetService, 
    llm_service_instance: llm_service.LLMService,
    user_group_link_service: UserGroupLinkService
):
    chat_id = message.chat.id
    text = message.text
    user_name = message.from_user.first_name
    is_group_chat = message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    chat_conf = config_manager.get_chat_config(chat_id)
    faq_found = False
    faq_answer_text = None
    response_text = None
    if faq_found and faq_answer_text:
        response_text = faq_answer_text
    else:
        personality_prompt_text = chat_conf.get("personality_prompt_text")
        if not personality_prompt_text or not personality_prompt_text.strip():
            logger.warning(f"Personality prompt text not found or empty for chat {chat_id}. Using fallback.")
            personality_prompt_text = "I'm here to help. How can I assist you?"
            logger.info(f"Using fallback personality prompt for chat {chat_id}: '{personality_prompt_text[:50]}...'")
        chat_history_text = None 
        reply_to_text_content = None
        reply_to_name_content = None
        if message.reply_to_message and message.reply_to_message.text:
            reply_to_text_content = message.reply_to_message.text
            reply_to_name_content = message.reply_to_message.from_user.first_name
            if message.reply_to_message.from_user.id == bot.id:
                reply_to_name_content = chat_conf.get("bot_display_name", "Helper Bot")
        try:
            generated_chat_response = await llm_service_instance.generate_chat_response(
                personality_prompt_text=personality_prompt_text,
                user_message=text,
                user_name=user_name,
                chat_history_text=chat_history_text,
                reply_to_text=reply_to_text_content,
                reply_to_name=reply_to_name_content
            )
        except Exception as e:
            logger.error(f"Error generating LLM chat response for chat {chat_id}: {e}", exc_info=True)
            generated_chat_response = None
        if generated_chat_response:
            response_text = generated_chat_response
        else:
            logger.warning(f"LLM failed to generate a chat response for chat {chat_id}.")
            response_text = "I'm not sure how to respond to that right now. You can try asking differently."
    cleaned_response = utils.remove_emojis(response_text)
    reply_markup = None
    if not is_group_chat:
        if chat_conf.get("anonq_enabled", True):
            reply_markup = inline_keyboards.get_after_faq_response_keyboard()
            await state.update_data(original_user_query_for_anon=text, original_chat_id_for_anon=chat_id)
    try:
        await message.reply(cleaned_response, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error sending message reply in chat {chat_id}: {e}", exc_info=True)


# --- Callback Query Handlers for User Actions ---

@router.callback_query(F.data == inline_keyboards.CALLBACK_USER_OK)
async def handle_user_ok_callback(query: CallbackQuery, state: FSMContext):
    await query.answer("Glad I could help!")
    try:
        # Edit the message to remove the keyboard
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logger.debug(f"Could not edit reply markup on user_ok callback: {e}")
    await state.clear() # Clear any state associated with this interaction


@router.callback_query(F.data == inline_keyboards.CALLBACK_USER_ASK_ANON)
async def handle_user_ask_anon_callback(
    query: CallbackQuery, 
    bot: Bot, 
    state: FSMContext, 
    llm_service_instance: llm_service.LLMService,
    user_group_link_service: UserGroupLinkService # Added service
):
    fsm_data = await state.get_data()
    original_query = fsm_data.get("original_user_query_for_anon")
    original_chat_id = fsm_data.get("original_chat_id_for_anon") # Chat where original query was made and button was shown

    current_user_id = query.from_user.id # User who clicked the button

    if not original_query:
        await query.answer("Sorry, I couldn't retrieve your original question.", show_alert=True)
        await query.message.edit_text("Something went wrong. Please try asking your question again.")
        await state.clear()
        return

    # Check appropriateness (remains the same)
    if not await llm_service_instance.is_text_appropriate(original_query):
        await query.answer("Message not sent.", show_alert=True)
        await query.message.edit_text(
            "Your question was deemed potentially inappropriate and was not forwarded.\n"
            "Please rephrase or reconsider your question."
        )
        if global_config.BOSS_ID:
            try:
                alert_message_to_boss = (
                    f"Potentially inappropriate anonymous question (via ASK_ANON button) blocked from user {current_user_id}.\n"
                    f"Original query context chat ID: {original_chat_id if original_chat_id else 'Unknown'}.\n"
                    f"User's message: {original_query}"
                )
                await bot.send_message(global_config.BOSS_ID, alert_message_to_boss)
            except Exception as e:
                logger.error(f"Failed to send inappropriate question alert to BOSS_ID: {e}")
        await state.clear()
        return

    # Get the target group ID from the UserGroupLinkService based on the user who clicked the button
    target_group_id = user_group_link_service.get_group_id_for_user(current_user_id)

    if target_group_id is None:
        await query.answer("No linked group found.", show_alert=True)
        await query.message.edit_text(
            "It seems you haven't linked a group chat for sending anonymous questions yet. "
            "Please go to our private chat and forward any message from your desired group to me to set it up."
        )
        logger.warning(f"User {current_user_id} clicked ASK_ANON but has no group linked. Original query from chat {original_chat_id}.")
        await state.clear()
        return
        
    # Formatting the message for the target group
    original_interaction_location = "their private chat with me" # Default
    if original_chat_id:
        try:
            chat_details = await bot.get_chat(original_chat_id)
            if chat_details.title:
                original_interaction_location = f"chat '{chat_details.title}'"
            elif chat_details.type == ChatType.PRIVATE:
                 original_interaction_location = "their private chat with me"
            else:
                original_interaction_location = f"chat ID {original_chat_id}"

        except Exception as e:
            logger.warning(f"Could not fetch title for original_chat_id {original_chat_id}: {e}")
            if original_chat_id == query.message.chat.id and query.message.chat.title:
                 original_interaction_location = f"chat '{query.message.chat.title}'"
            elif query.message.chat.type != ChatType.PRIVATE:
                 original_interaction_location = f"chat ID {query.message.chat.id}"

    formatted_message_for_target_group = Text(
        Bold("🗣️ New Anonymous Question"), "\n\n",
        "Question:\n",
        ExpandableBlockQuote(original_query) 
    )

    try:
        await bot.send_message(target_group_id, **formatted_message_for_target_group.as_kwargs())
        await query.answer("Question sent anonymously!", show_alert=True)
        await query.message.edit_text("Your question has been sent anonymously to your linked group.")
        logger.info(f"User {current_user_id} (via ASK_ANON) sent anonymous question to linked group {target_group_id}: '{original_query[:50]}...'")
    except Exception as e:
        logger.error(f"Failed to send anonymous question (via ASK_ANON) to linked group {target_group_id} for user {current_user_id}: {e}")
        await query.answer("Error sending question.", show_alert=True)
        if "bot was kicked" in str(e).lower() or "chat not found" in str(e).lower() or "bot is not a member" in str(e).lower():
             await query.message.edit_text("Sorry, I couldn't send your question. I might no longer be a member of your linked group. Please try re-linking your group by forwarding a message from it to our PM.")
        else:
            await query.message.edit_text("Sorry, there was an error sending your anonymous question. Please try again later.")

    await state.clear()


logger.info("User command and callback handlers registered.")
