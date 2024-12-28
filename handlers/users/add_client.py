import asyncio
import re
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from aiogram import Router, types
from loader import bot, db
from filters.admin import IsBotAdminFilter
from data.config import ADMINS
from aiogram.fsm.context import FSMContext
from states.add_client import AddClient

router = Router()
RETRY_DELAY = 5
PHONE_REGEX = r"^\+?[1-9]\d{1,14}$"  # E.164 format uchun regex

def format_phone_number(phone: str) -> str:
    phone = ''.join(filter(lambda x: x.isdigit() or x == '+', phone))
    if not phone.startswith('+'):
        phone = '+998' + phone
    return phone

async def create_client_session(api_id: int, api_hash: str):
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    return client



async def delete_message_later(chat_id, message_id, delay=5):
    """Delay bilan xabarni o'chiradi."""
    await asyncio.sleep(delay)
    await bot.delete_message(chat_id=chat_id, message_id=message_id)

async def send_new_code(client, phone):
    """Yangi kodni yuboradi."""
    await asyncio.sleep(RETRY_DELAY)
    return await client.send_code_request(phone)

@router.callback_query(lambda call: call.data == "add_client", IsBotAdminFilter(ADMINS))
async def add_telegram_client_id(call: types.CallbackQuery, state: FSMContext):
    """API ID kiritishni boshlaydi."""
    await call.answer(text="Ikkinchi bosqichli tekshiruv parolini o'chirishni unutmang ❗")
    await state.set_state(AddClient.api_id)
    await bot.send_message(chat_id=call.from_user.id, text="\U0001F194 API ID yozing \U0001F447")
    # await delete_message_later(chat_id=call.from_user.id, message_id=rm.message_id)

@router.message(AddClient.api_id, IsBotAdminFilter(ADMINS))
async def update_telegram_client_id(message: types.Message, state: FSMContext):
    """API ID ni saqlaydi va API Hash so'raydi."""
    await state.update_data(api_id=message.text)
    await message.answer(text="\u2705 API ID yuklandi.")
    await bot.send_message(chat_id=message.from_user.id, text="\u2699 API Hash yozing \U0001F447")
    # await delete_message_later(chat_id=message.from_user.id, message_id=rm.message_id)
    await state.set_state(AddClient.api_hash)

@router.message(AddClient.api_hash, IsBotAdminFilter(ADMINS))
async def update_telegram_client_hash(message: types.Message, state: FSMContext):
    """API Hash ni saqlaydi va telefon raqamini so'raydi."""
    await state.update_data(api_hash=message.text)
    await message.answer(text="\u2705 API Hash yuklandi.")
    await bot.send_message(chat_id=message.from_user.id, text="\U0001F4DE Telefon raqam yozing \U0001F447")
    # await delete_message_later(chat_id=message.from_user.id, message_id=rm.message_id)
    await state.set_state(AddClient.phone)

@router.message(AddClient.phone, IsBotAdminFilter(ADMINS))
async def update_telegram_client_phone(message: types.Message, state: FSMContext):
    status_msg = await message.answer("\U0001F504 Telefon raqam tekshirilmoqda...")
    
    user_data = await state.get_data()
    api_id = int(user_data.get("api_id"))
    api_hash = user_data.get("api_hash")
    phone = format_phone_number(message.text.strip())

    if not re.match(PHONE_REGEX, phone):
        await status_msg.edit_text("\u274C Noto'g'ri format. Masalan: +998901234567")
        await state.clear()
        return

    try:
        client = await create_client_session(api_id, api_hash)
        
        if not await client.is_user_authorized():
            send_code_result = await client.send_code_request(phone)
            await state.update_data(
                phone=phone,
                phone_code_hash=send_code_result.phone_code_hash,
                client=client
            )
            
            await status_msg.edit_text(
                f"\U0001F4F1 <b>{phone}</b> raqamiga kod yuborildi.\n"
                "Telegramdan kelgan kodni kiriting\n Kelgan kod oldidan ushbu belgini qo'shing (_):\n Misol uchun:  _54827",
                parse_mode="HTML"
            )
            await state.set_state(AddClient.otp)
        
    except errors.PhoneNumberInvalidError:
        await status_msg.edit_text("\u274C Noto'g'ri telefon raqam")
        await state.clear()
    except Exception as e:
        await status_msg.edit_text(f"\u274C Xatolik: {str(e)}")
        await state.clear()

@router.message(AddClient.otp, IsBotAdminFilter(ADMINS))
async def process_otp_code(message: types.Message, state: FSMContext):
    status_msg = await message.answer("\U0001F504 Kod tekshirilmoqda...")
    
    user_data = await state.get_data()
    phone = user_data.get("phone")
    phone_code_hash = user_data.get("phone_code_hash")
    client = user_data.get("client")
    otp = message.text.strip()
    otp_clear = otp.replace('_', '')

    try:
        # Sign in with the provided code
        await client.sign_in(
            phone=phone,
            code=otp_clear,
            phone_code_hash=phone_code_hash
        )
        
        # Get session string after successful authentication
        session_string = client.session.save()
        
        # Save to database
        await db.add_client(
            api_id=user_data.get("api_id"),
            api_hash=user_data.get("api_hash"),
            phone=phone,
            stringsession=session_string
        )

        await status_msg.edit_text(
            "\u2705 Muvaffaqiyatli ulandi!\n\n"
            f"\U0001F4F1 Telefon: {phone}\n"
            f"\U0001F511 API ID: {user_data.get('api_id')}\n\n"
            f"\U0001F512 Session:\n<code>{session_string}</code>",
            parse_mode="HTML"
        )

    except errors.SessionPasswordNeededError:
        await status_msg.edit_text("\U0001F511 2FA parolini kiriting:")
        await state.set_state(AddClient.password)
        
    except errors.PhoneCodeExpiredError:
        # Handle expired code by requesting a new one
        try:
            await asyncio.sleep(RETRY_DELAY)
            send_code_result = await client.send_code_request(phone)
            await state.update_data(phone_code_hash=send_code_result.phone_code_hash)
            await status_msg.edit_text("\U0001F504 Yangi kod yuborildi. Uni kiriting:")
        except Exception as e:
            await status_msg.edit_text(f"\u274C Yangi kod yuborishda xatolik: {str(e)}")
            await state.clear()
            
    except errors.PhoneCodeInvalidError:
        await status_msg.edit_text("\u274C Noto'g'ri kod. Qayta urinib ko'ring")
    except Exception as e:
        await status_msg.edit_text(f"\u274C Xatolik: {str(e)}")
        await state.clear()
    finally:
        if not await client.is_user_authorized():
            await client.disconnect()

@router.message(AddClient.password, IsBotAdminFilter(ADMINS))
async def process_password(message: types.Message, state: FSMContext):
    status_msg = await message.answer("\U0001F504 Parol tekshirilmoqda...")
    
    user_data = await state.get_data()
    client = user_data.get("client")

    try:
        await client.sign_in(password=message.text.strip())
        session_string = client.session.save()
        
        await db.add_client(
            api_id=user_data.get("api_id"),
            api_hash=user_data.get("api_hash"),
            phone=user_data.get("phone"),
            stringsession=session_string
        )

        await status_msg.edit_text(
            "\u2705 2FA tekshiruvi muvaffaqiyatli!\n\n"
            f"\U0001F4F1 Telefon: {user_data.get('phone')}\n"
            f"\U0001F511 API ID: {user_data.get('api_id')}\n\n"
            f"\U0001F512 Session:\n<code>{session_string}</code>",
            parse_mode="HTML"
        )

    except errors.PasswordHashInvalidError:
        await status_msg.edit_text("\u274C Noto'g'ri parol")
    except Exception as e:
        await status_msg.edit_text(f"\u274C Xatolik: {str(e)}")
    finally:
        await client.disconnect()
        await state.clear()