from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from filters.admin import IsBotAdminFilter
from loader import db, bot
from data.config import ADMINS

router = Router()


@router.callback_query(lambda c: c.data == "rm_list_clients", IsBotAdminFilter(ADMINS))
async def list_all_clients(call: types.CallbackQuery):
    """Barcha mijozlarni ko'rsatish"""
    clients = await db.get_all_clients()

    if not clients:
        await call.answer("Hozircha akkauntlar yo'q!", show_alert=True)
        return

    for client in clients:
        phone = client.get('phone', 'Noma\'lum')
        api_id = client.get('api_id', 'Noma\'lum')
        is_active = "✅ Faol" if client.get('is_active') else "❌ Faol emas"
        is_banned = "🚫 Banlangan" if client.get('is_banned') else "✅ Banlanmagan"

        text = (
            f"📱 Telefon: {phone}\n"
            f"🔑 API ID: {api_id}\n"
            f"Holati: {is_active}\n"
            f"Ban holati: {is_banned}\n"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ O'chirish",
                        callback_data=f"delete_client:{client['id']}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Aktivlashtirish" if not client['is_active'] else "🔄 Deaktivlashtirish",
                        callback_data=f"toggle_client:{client['id']}"
                    )
                ]
            ]
        )

        await call.message.answer(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("delete_client:"), IsBotAdminFilter(ADMINS))
async def delete_client(call: types.CallbackQuery):
    """Mijozni o'chirish"""
    client_id = int(call.data.split(":")[1])

    try:
        # Tekshirish uchun keyboard
        confirm_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Ha",
                        callback_data=f"confirm_delete:{client_id}"
                    ),
                    InlineKeyboardButton(
                        text="❌ Yo'q",
                        callback_data=f"cancel_delete:{client_id}"
                    )
                ]
            ]
        )

        await call.message.edit_text(
            "Akkauntni o'chirishni tasdiqlaysizmi?",
            reply_markup=confirm_keyboard
        )

    except Exception as e:
        await call.answer(f"Xatolik yuz berdi: {str(e)}", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("confirm_delete:"), IsBotAdminFilter(ADMINS))
async def confirm_delete_client(call: types.CallbackQuery):
    """Mijozni o'chirishni tasdiqlash"""
    client_id = int(call.data.split(":")[1])

    try:
        # Mijozni o'chirish
        await db.execute(
            "DELETE FROM Clients WHERE id = $1",
            client_id,
            execute=True
        )

        # Related userslarning active_client_session ni null qilish
        await db.execute(
            "UPDATE Users SET active_client_session = NULL WHERE active_client_session = $1",
            client_id,
            execute=True
        )

        await call.message.edit_text("✅ Akkaunt muvaffaqiyatli o'chirildi!")
        await call.answer("Akkaunt o'chirildi!", show_alert=True)

    except Exception as e:
        await call.answer(f"Xatolik yuz berdi: {str(e)}", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("cancel_delete:"), IsBotAdminFilter(ADMINS))
async def cancel_delete_client(call: types.CallbackQuery):
    """Mijozni o'chirishni bekor qilish"""
    await call.message.delete()
    await call.answer("O'chirish bekor qilindi!", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("toggle_client:"), IsBotAdminFilter(ADMINS))
async def toggle_client_status(call: types.CallbackQuery):
    """Mijoz statusini o'zgartirish"""
    client_id = int(call.data.split(":")[1])

    try:
        # Hozirgi statusni olish
        client = await db.execute(
            "SELECT is_active FROM Clients WHERE id = $1",
            client_id,
            fetchrow=True
        )

        if client:
            new_status = not client['is_active']

            # Statusni yangilash
            await db.execute(
                "UPDATE Clients SET is_active = $1 WHERE id = $2",
                new_status,
                client_id,
                execute=True
            )

            status_text = "aktivlashtirildi" if new_status else "deaktivlashtirildi"
            await call.answer(f"Akkaunt {status_text}!", show_alert=True)

            # Xabarni yangilash
            await list_all_clients(call)

    except Exception as e:
        await call.answer(f"Xatolik yuz berdi: {str(e)}", show_alert=True)