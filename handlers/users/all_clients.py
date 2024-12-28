from aiogram import types, Router
from filters.admin import IsBotAdminFilter
from data.config import ADMINS
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import db

router = Router()


@router.callback_query(lambda call: call.data == "list_accounts", IsBotAdminFilter(ADMINS))
async def list_active_clients(call: types.CallbackQuery):
    try:
        # Barcha aktiv klientlarni olish
        clients = await db.get_all_clients()
        if not clients:
            await call.message.answer("🚫 Aktiv klientlar mavjud emas.")
            return

        # Foydalanuvchining aktiv klient sessiyasini olish
        result = await db.execute(
            "SELECT active_client_session FROM Users WHERE telegram_id = $1",
            call.from_user.id,
            fetch=True
        )

        # Ma'lumotni to'g'ri formatda ajratish
        active_client_id = result[0]['active_client_session'] if result and result[0]['active_client_session'] else None

        # Inline tugmalarni yaratish
        buttons = []
        for client in clients:
            phone = client['phone']
            client_id = client['id']
            button_text = f"✔ {phone}" if client_id == active_client_id else phone
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"switch_client:{client_id}"
            )])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await call.message.answer("Aktiv klientlar ro'yxati:", reply_markup=keyboard)
        await call.answer()

    except Exception as e:
        await call.message.answer(f"❌ Xatolik yuz berdi: {e}")
        await call.answer()


@router.callback_query(lambda call: call.data.startswith("switch_client"), IsBotAdminFilter(ADMINS))
async def switch_client_handler(call: types.CallbackQuery):
    try:
        user_id = call.from_user.id
        client_id = int(call.data.split(":")[1])

        # Aktiv klient sessiyasini almashtirish
        result = await db.execute(
            "UPDATE Users SET active_client_session = $1 WHERE telegram_id = $2 RETURNING id",
            client_id, user_id,
            fetch=True
        )

        if result:
            await call.answer("✅ Aktiv klient muvaffaqiyatli o'zgartirildi", show_alert=True)
            # Yangilangan ro'yxatni ko'rsatish
            await list_active_clients(call)
        else:
            await call.answer("❌ Klient o'zgartirishda xatolik yuz berdi", show_alert=True)

    except Exception as e:
        await call.message.answer(f"❌ Xatolik yuz berdi: {e}")
        await call.answer()
