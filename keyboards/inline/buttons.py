from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


inline_keyboard = [[
    InlineKeyboardButton(text="✅ Yes", callback_data='yes'),
    InlineKeyboardButton(text="❌ No", callback_data='no')
]]
are_you_sure_markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def main_menu():
    mk_menu = [
        [InlineKeyboardButton(text="➕ Akkaunt qo'shish", callback_data="add_client"),
         InlineKeyboardButton(text="🗑 Akkaunt o'chirish", callback_data="rm_list_clients")],

        [InlineKeyboardButton(text="🖼 Barcha reklamalar", callback_data="list_advertisement"),
         InlineKeyboardButton(text="📩 Reklama bo'limi", callback_data="send_advertisement")],

        [InlineKeyboardButton(text="⛔ Ban akkauntlarni ko'rish", callback_data="view_banned"),
         InlineKeyboardButton(text="⏱ Spam akkauntni tekshirish", callback_data="check_spam")],

        [InlineKeyboardButton(text="🔄 Botni qayta ishga tushirish", callback_data="restart_bot"), InlineKeyboardButton(text="📊 Statistika", callback_data='statistika')],
        [InlineKeyboardButton(text="⚙ Sozlamalar", callback_data='settings'), InlineKeyboardButton(text="💱 Akkaunt almashtirish", callback_data='list_accounts')]

    ]

    keyboards = InlineKeyboardMarkup(inline_keyboard=mk_menu)
    return keyboards

