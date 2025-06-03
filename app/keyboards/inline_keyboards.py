from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

CALLBACK_USER_OK = "user_ack_ok"
CALLBACK_USER_ASK_ANON = "user_ask_anon"

def get_after_faq_response_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Мне помог ответ, спасибо!", callback_data=CALLBACK_USER_OK)
    builder.button(text="Анонимно спросить кураторов", callback_data=CALLBACK_USER_ASK_ANON)
    builder.adjust(1)
    return builder.as_markup()

if __name__ == '__main__':
    kb = get_after_faq_response_keyboard()
    for row in kb.inline_keyboard:
        for button in row:
            print(f"Text: {button.text}, Callback Data: {button.callback_data}")
