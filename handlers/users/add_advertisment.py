import html
from aiogram import types, Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from telethon.sessions import StringSession
from telethon.sync import TelegramClient
from loader import db, bot
import logging

router = Router()
PAGE_SIZE = 5


class CreateAdvertisementStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_text = State()
    selecting_duration = State()
    selecting_groups = State()


def sanitize_text(text):
    if not text:
        return text
    clean_text = text.replace("<record>", "").replace("</record>", "")
    clean_text = clean_text.replace("<script>", "").replace("</script>", "")
    return html.escape(clean_text)


def sanitize_group_title(title):
    if not title:
        return "Nomsiz guruh"
    return html.escape(str(title))[:50]


@router.callback_query(lambda call: call.data == "send_advertisement")
async def start_create_ad(call: types.CallbackQuery, state: FSMContext):
    active_client = await db.get_active_client(call.from_user.id)
    if not active_client:
        await call.message.answer("❌ Aktiv sessiya topilmadi! Iltimos avval sessiyani yarating.", parse_mode="HTML")
        return

    await call.message.answer(
        "📸 Reklama uchun rasm yuboring.\n"
        "Rasmsiz davom etish uchun /continue\n"
        "Bekor qilish uchun /cancel", 
        parse_mode="HTML"
    )
    await state.set_state(CreateAdvertisementStates.waiting_for_photo)


@router.message(Command('cancel'))
async def cancel_creation(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Reklama yaratish bekor qilindi.", parse_mode="HTML")


@router.message(Command('continue'))
async def skip_photo(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == CreateAdvertisementStates.waiting_for_photo:
        # Rasmsiz davom etish
        await state.update_data(photo_id=None, file_path=None)
        await message.answer("✍️ Endi reklama matnini yuboring.\nBekor qilish uchun /cancel", parse_mode="HTML")
        await state.set_state(CreateAdvertisementStates.waiting_for_text)


@router.message(CreateAdvertisementStates.waiting_for_photo, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id

    try:
        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path

        await state.update_data(
            photo_id=file_id,
            file_path=file_path
        )

        await message.answer("✍️ Endi reklama matnini yuboring.\nBekor qilish uchun /cancel", parse_mode="HTML")
        await state.set_state(CreateAdvertisementStates.waiting_for_text)

    except Exception as e:
        logging.error(f"Error handling photo: {str(e)}")
        await message.answer("❌ Rasmni saqlashda xatolik yuz berdi. Qaytadan urinib ko'ring.", parse_mode="HTML")
        await state.clear()


@router.message(CreateAdvertisementStates.waiting_for_text)
async def handle_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)

    durations = [15, 30, 60, 120]
    buttons = [
        [InlineKeyboardButton(text=f"⏱ {duration} daqiqa", callback_data=f"set_duration:{duration}")]
        for duration in durations
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("⏱ Reklama davomiyligini tanlang:", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(CreateAdvertisementStates.selecting_duration)


@router.callback_query(CreateAdvertisementStates.selecting_duration)
async def handle_duration(call: types.CallbackQuery, state: FSMContext):
    try:
        duration = int(call.data.split(":")[1])
        await state.update_data(duration=duration)

        active_client_id = await db.get_active_client(call.from_user.id)
        if not active_client_id:
            await call.message.answer("❌ Aktiv sessiya topilmadi!", parse_mode="HTML")
            return

        active_client = await db.execute(
            "SELECT api_id, api_hash, stringsession FROM Clients WHERE id = $1;",
            active_client_id,
            fetchrow=True
        )
        if not active_client:
            await call.message.answer("❌ Klient ma'lumotlari topilmadi!", parse_mode="HTML")
            return

        async with TelegramClient(
                StringSession(active_client["stringsession"]),
                int(active_client["api_id"]),
                active_client["api_hash"]
        ) as client:
            dialogs = await client.get_dialogs()
            groups = [
                {"id": dialog.id, "title": sanitize_group_title(dialog.title)}
                for dialog in dialogs if dialog.is_group or dialog.is_channel
            ]

        if not groups:
            await call.message.answer("🚫 Guruhlar topilmadi.", parse_mode="HTML")
            return

        await state.update_data(available_groups=groups, selected_groups=[])
        await call.message.answer("📢 Reklama uchun guruhlarni tanlashni boshlang.", parse_mode="HTML")
        await show_groups_page(call.message, state, page=0)
        await state.set_state(CreateAdvertisementStates.selecting_groups)

    except Exception as e:
        await call.message.answer(f"❌ Xatolik yuz berdi: {str(e)}", parse_mode="HTML")

async def show_groups_page(message: types.Message, state: FSMContext, page: int):
    data = await state.get_data()
    groups = data.get("available_groups", [])
    selected_groups = data.get("selected_groups", [])

    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(groups))
    current_page_groups = groups[start:end]

    buttons = []
    for group in current_page_groups:
        group_id = group['id']
        group_title = group['title']
        selected = "✅" if group_id in selected_groups else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{selected} 📢 {group_title}",
                callback_data=f"select_group:{group_id}"
            )
        ])

    navigation_buttons = []
    if start > 0:
        navigation_buttons.append(
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"show_groups:{page - 1}")
        )
    if end < len(groups):
        navigation_buttons.append(
            InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"show_groups:{page + 1}")
        )

    if navigation_buttons:
        buttons.append(navigation_buttons)

    buttons.append([
        InlineKeyboardButton(text="✅ Tanlash tugadi", callback_data="finish_selection")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.edit_text("📢 Reklama uchun guruhlarni tanlang:", reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(CreateAdvertisementStates.selecting_groups, lambda call: call.data.startswith("show_groups:"))
async def handle_group_pagination(call: types.CallbackQuery, state: FSMContext):
    page = int(call.data.split(":")[1])
    await show_groups_page(call.message, state, page)


@router.callback_query(CreateAdvertisementStates.selecting_groups, lambda call: call.data.startswith("select_group:"))
async def handle_group_selection(call: types.CallbackQuery, state: FSMContext):
    group_id = int(call.data.split(":")[1])
    data = await state.get_data()
    selected_groups = data.get("selected_groups", [])

    if group_id in selected_groups:
        selected_groups.remove(group_id)
        await call.answer("❌ Guruh o'chirildi")
    else:
        selected_groups.append(group_id)
        await call.answer("✅ Guruh qo'shildi")

    await state.update_data(selected_groups=selected_groups)
    current_page = len(selected_groups) // PAGE_SIZE
    await show_groups_page(call.message, state, current_page)


@router.callback_query(CreateAdvertisementStates.selecting_groups, lambda call: call.data == "finish_selection")
async def finish_group_selection(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_groups = data.get("selected_groups", [])

    if not selected_groups:
        await call.answer("❌ Hech bo'lmaganda bitta guruh tanlang!", show_alert=True)
        return

    try:
        photo_id = data.get("photo_id")  # Endi photo_id None bo'lishi mumkin
        text = sanitize_text(data.get("text", ""))
        duration = data.get("duration")
        created_by = call.from_user.id
        if photo_id == None:
            advertisement = await db.add_advertisement(
                text=text,
                duration_minutes=duration,
                created_by=created_by,
                group_ids=selected_groups
            )
        else:
            advertisement = await db.add_advertisement(
                photo_id=photo_id,
                text=text,
                duration_minutes=duration,
                created_by=created_by,
                group_ids=selected_groups
            )

        if advertisement:
            await call.message.answer("✅ Reklama muvaffaqiyatli yaratildi va saqlandi.", parse_mode="HTML")
        else:
            await call.message.answer("❌ Reklama saqlashda xatolik yuz berdi.", parse_mode="HTML")

    except Exception as e:
        await call.message.answer(f"❌ Xatolik yuz berdi: {str(e)}", parse_mode="HTML")

    finally:
        await state.clear()
