import datetime

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.session.middlewares.request_logging import logger
from loader import db, bot
from data.config import ADMINS
from utils.shortcuts import safe_markdown
from keyboards.inline.buttons import main_menu
# from keyboards.reply.menu import main_kb
from loader import bot, db
from filters.admin import IsBotAdminFilter
router = Router()
# ADMINS = [5842679273, 5361295856]


@router.message(CommandStart(), IsBotAdminFilter(ADMINS))
async def do_start(message: types.Message):
    """
    Handles the /start command. Checks if the user exists in the database and welcomes them accordingly.
    """
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username
    clients_counter = await db.count_clients()
    user = await db.select_user(telegram_id=telegram_id)
    if user:
        await bot.send_message(chat_id=message.from_user.id, text=f"Assalomu alaykum ADMIN 👋 Boshqaruv paneli bilan tanishing!", reply_markup=main_menu())
        await bot.send_message(chat_id=message.from_user.id, text=f"🤖 Jami clientlar soni: {clients_counter}\n"
                                                                  f"🔐 Jami Spam clientlar: 0\n"
                                                                  f"❌ Jami Ban clientlar: 0\n"
                                                                  f"👥 Yuklab olingan jami foydalanuvchilar: 0")
    else:
        await db.add_user(full_name=full_name, username=username, telegram_id=telegram_id)
        await bot.send_message(chat_id=message.from_user.id, text="😊 Qaytganingiz bilan Admin! Bazaga yozib qo'ydim... \nBoshqaruv paneli bilan tanishing!", reply_markup=main_menu())
        await bot.send_message(chat_id=message.from_user.id, text=f"🤖 Jami clientlar soni: {clients_counter}\n"
                                                                  f"🔐 Jami Spam clientlar: 0\n"
                                                                  f"❌ Jami Ban clientlar: 0\n"
                                                                  f"👥 Yuklab olingan jami foydalanuvchilar: 0")