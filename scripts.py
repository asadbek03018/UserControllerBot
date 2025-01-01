import asyncio
import logging
from datetime import datetime
from telethon.sessions import StringSession
from telethon.sync import TelegramClient
from telethon.tl.types import InputPhoto, Message
from loader import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdvertisementScheduler:
    def __init__(self):
        self.is_running = False
        self.active_tasks = {}

    async def start(self):
        """Schedulerni ishga tushirish"""
        if self.is_running:
            return
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self.schedule_advertisements())
        logger.info("Reklama tarqatuvchi ishga tushirildi.")

    async def stop(self):
        """Schedulerni to'xtatish"""
        self.is_running = False
        if hasattr(self, "scheduler_task"):
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                logger.info("Reklama tarqatuvchi to'xtatildi.")

    async def get_photo_access_hash(self, client: TelegramClient, message_id: int) -> dict:
        """Rasmning access_hash ma'lumotlarini olish"""
        try:
            # Get message by its ID from user's own messages
            message = await client.get_messages('me', ids=message_id)

            if not message or not message.photo:
                logger.error(f"Message {message_id} not found or contains no photo")
                return None

            photo = message.photo
            return {
                "id": photo.id,
                "access_hash": photo.access_hash,
                "file_reference": photo.file_reference,
                "message_id": message_id
            }
        except Exception as e:
            logger.error(f"Rasmni olishda xatolik: {str(e)}")
            return None

    async def retry_send_photo(self, client: TelegramClient, group_id: int, photo_id: int, text: str):
        """Rasmni qayta yuborish (file_reference eskirganda)"""
        try:
            message = await client.get_messages(None, ids=photo_id)
            if message and message.media:
                await client.send_file(
                    group_id,
                    file=message.media,
                    caption=text,
                    parse_mode='html'
                )
                return True
        except Exception as e:
            logger.error(f"Rasmni qayta yuborishda xatolik: {str(e)}")
            return False

    async def send_advertisement(self, client: TelegramClient, group_id: int, photo_data: dict, text: str):
        """Rasm yoki matnni yuborish"""
        try:
            if photo_data:
                try:
                    # First try to get the message and send directly
                    message = await client.get_messages('me', ids=photo_data["message_id"])
                    if message and message.photo:
                        await client.send_file(
                            group_id,
                            file=message.photo,
                            caption=text,
                            parse_mode='html'
                        )
                    else:
                        # Fallback to sending just the text if photo is not found
                        logger.warning(f"Photo not found for message {photo_data['message_id']}, sending text only")
                        await client.send_message(group_id, text, parse_mode='html')
                except Exception as e:
                    logger.error(f"Error sending photo: {str(e)}")
                    # Fallback to sending text only
                    await client.send_message(group_id, text, parse_mode='html')
            else:
                await client.send_message(group_id, text, parse_mode='html')

            await self.log_sent_advertisement(group_id)
            logger.info(f"Reklama yuborildi: guruh={group_id}")

        except Exception as e:
            logger.error(f"Reklamani yuborishda xatolik: guruh={group_id}, xato={str(e)}")
            raise e



    async def process_advertisement(self, ad: dict):
        """Bitta reklamani qayta ishlash"""
        try:
            client_info = await db.get_client_for_advertisement(ad["created_by"])
            if not client_info:
                logger.error(f"Foydalanuvchi uchun aktiv client topilmadi: {ad['created_by']}")
                return

            async with TelegramClient(
                    StringSession(client_info["stringsession"]),
                    int(client_info["api_id"]),
                    client_info["api_hash"]
            ) as client:
                await client.connect()

                if not await client.is_user_authorized():
                    logger.error(f"Client avtorizatsiyadan o'tmagan: {ad['created_by']}")
                    return

                photo_data = None
                if ad["photo_id"]:
                    photo_data = await self.get_photo_access_hash(client, ad["photo_id"])
                    if not photo_data:
                        logger.error(f"Rasm ma'lumotlarini olishda xatolik: {ad['id']}")
                        return

                for group_id in ad["group_ids"]:
                    try:
                        await self.send_advertisement(client, group_id, photo_data, ad["text"])
                        await asyncio.sleep(2)  # Guruhlar orasida kutish
                    except Exception as e:
                        logger.error(f"Guruhga yuborishda xatolik: guruh={group_id}, xato={str(e)}")
                        continue

        except Exception as e:
            logger.error(f"Reklamani qayta ishlashda xatolik: reklama={ad['id']}, xato={str(e)}")

    async def schedule_advertisements(self):
        """Reklamalarni rejalashtirish"""
        while self.is_running:
            try:
                current_time = datetime.now()
                ads = await self.get_active_advertisements()

                for ad in ads:
                    if await self.should_send_advertisement(ad, current_time):
                        if ad["id"] not in self.active_tasks or self.active_tasks[ad["id"]].done():
                            task = asyncio.create_task(self.process_advertisement(ad))
                            self.active_tasks[ad["id"]] = task

                # Keyingi tekshirish vaqtini hisoblash
                next_check = min(60, min((ad["duration_minutes"] for ad in ads), default=60))
                await asyncio.sleep(next_check)

                # Tugallangan tasklarni tozalash
                completed_tasks = [ad_id for ad_id, task in self.active_tasks.items() if task.done()]
                for ad_id in completed_tasks:
                    task = self.active_tasks.pop(ad_id)
                    try:
                        # Taskda xatolik bo'lgan bo'lsa, uni log qilish
                        exc = task.exception()
                        if exc:
                            logger.error(f"Task xatolik bilan tugadi: reklama={ad_id}, xato={str(exc)}")
                    except asyncio.CancelledError:
                        pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler asosiy tsiklida xatolik: {str(e)}")
                await asyncio.sleep(60)

    async def should_send_advertisement(self, ad: dict, current_time: datetime) -> bool:
        """Reklamani yuborish kerakligini tekshirish"""
        last_sent = ad.get("last_sent")
        duration_minutes = ad["duration_minutes"]

        if not last_sent:
            return True

        elapsed_minutes = (current_time - last_sent).total_seconds() / 60
        return elapsed_minutes >= duration_minutes

    async def get_active_advertisements(self) -> list:
        """Faol reklamalarni olish"""
        query = """
        SELECT 
            a.id, 
            a.photo_id, 
            a.text, 
            a.duration_minutes, 
            a.created_by, 
            a.group_ids, 
            a.created_at, 
            a.is_active, 
            COALESCE(MAX(l.sent_at), a.created_at) as last_sent
        FROM Advertisements a
        LEFT JOIN AdvertisementLogs l ON a.id = l.ad_id
        WHERE a.is_active = TRUE
        GROUP BY a.id
        """
        try:
            ads = await db.execute(query, fetch=True)
            logger.debug(f"Faol reklamalar soni: {len(ads)}")
            return ads
        except Exception as e:
            logger.error(f"Reklamalarni olishda xatolik: {str(e)}")
            return []