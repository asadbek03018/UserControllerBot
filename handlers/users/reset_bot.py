import os
import sys
from aiogram import Router, types
from aiogram.filters import Command
from filters.admin import IsBotAdminFilter
from data.config import ADMINS
from loader import bot

router = Router()


@router.message(Command('restart'), IsBotAdminFilter(ADMINS))
async def restart_bot(message: types.Message):
    """Botni qayta ishga tushirish"""
    await message.answer("🔄 Bot qayta ishga tushirilmoqda...")

    try:
        # Barcha active connectionlarni yopish
        await bot.session.close()

        # Pythonni qayta ishga tushirish
        python = sys.executable
        os.execl(python, python, *sys.argv)

    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")


@router.callback_query(lambda c: c.data == "restart_bot", IsBotAdminFilter(ADMINS))
async def restart_bot_callback(call: types.CallbackQuery):
    """Inline tugma orqali botni qayta ishga tushirish"""
    await call.answer("🔄 Bot qayta ishga tushirilmoqda...", show_alert=True)

    try:
        # Barcha active connectionlarni yopish
        await bot.session.close()

        # Pythonni qayta ishga tushirish
        python = sys.executable
        os.execl(python, python, *sys.argv)

    except Exception as e:
        await call.message.answer(f"❌ Xatolik yuz berdi: {str(e)}")