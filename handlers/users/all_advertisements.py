from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import db

router = Router()

# Har bir sahifada ko'rsatiladigan reklamalar soni
ADS_PER_PAGE = 5


async def get_page_ads(page: int):
    """Berilgan sahifa uchun reklamalarni olish"""
    offset = (page - 1) * ADS_PER_PAGE
    query = """
        SELECT id, photo_id, text, duration_minutes, created_at
        FROM Advertisements
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
    """
    return await db.execute(query, ADS_PER_PAGE, offset, fetch=True)


async def get_total_pages():
    """Jami sahifalar sonini hisoblash"""
    total_ads = await db.execute("SELECT COUNT(*) FROM Advertisements", fetchval=True)
    return (total_ads + ADS_PER_PAGE - 1) // ADS_PER_PAGE


@router.callback_query(lambda c: c.data == "list_advertisement")
async def show_advertisements(call: types.CallbackQuery):
    """Reklamalar ro'yxatini ko'rsatish"""
    await show_ads_page(call, 1)


@router.callback_query(lambda c: c.data.startswith("ads_page:"))
async def handle_pagination(call: types.CallbackQuery):
    """Sahifalarni boshqarish"""
    page = int(call.data.split(":")[1])
    await show_ads_page(call, page)


async def show_ads_page(call: types.CallbackQuery, page: int):
    """Berilgan sahifadagi reklamalarni ko'rsatish"""
    ads = await get_page_ads(page)
    total_pages = await get_total_pages()

    if not ads:
        await call.message.edit_text("Reklamalar topilmadi!")
        return

    for ad in ads:
        # Reklama matni
        text = f"📝 Reklama #{ad['id']}\n\n"
        text += f"Matn: {ad['text'][:100]}...\n"
        text += f"⏰ Davomiyligi: {ad['duration_minutes']} daqiqa\n"
        text += f"📅 Yaratilgan vaqt: {ad['created_at'].strftime('%Y-%m-%d %H:%M')}"

        # Reklama uchun tugmalar
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ O'chirish", callback_data=f"delete_ad:{ad['id']}")]
        ])

        # Agar reklama rasmi bo'lsa, rasm bilan yuborish
        if ad['photo_id']:
            await call.message.answer_photo(
                photo=ad['photo_id'],
                caption=text,
                reply_markup=keyboard
            )
        else:
            await call.message.answer(text, reply_markup=keyboard)

    # Pagination tugmalari
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(
            InlineKeyboardButton("⬅️ Oldingi", callback_data=f"ads_page:{page - 1}")
        )
    if page < total_pages:
        pagination_buttons.append(
            InlineKeyboardButton("Keyingi ➡️", callback_data=f"ads_page:{page + 1}")
        )

    if pagination_buttons:
        await call.message.answer(
            f"Sahifa: {page}/{total_pages}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[pagination_buttons])
        )


@router.callback_query(lambda c: c.data.startswith("delete_ad:"))
async def delete_advertisement(call: types.CallbackQuery):
    """Reklamani o'chirish"""
    ad_id = int(call.data.split(":")[1])

    try:
        await db.execute("DELETE FROM Advertisements WHERE id = $1", ad_id, execute=True)
        await call.answer("✅ Reklama muvaffaqiyatli o'chirildi!", show_alert=True)
        # Xabarni o'chirish
        await call.message.delete()
    except Exception as e:
        await call.answer("❌ Xatolik yuz berdi!", show_alert=True)