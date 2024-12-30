import asyncio
import logging
from telethon.sessions import StringSession
from telethon.sync import TelegramClient
from telethon.tl.types import InputPhoto
from loader import db  # O'z ma'lumotlar bazangiz uchun

class AdvertisementHandler:
    def __init__(self):
        self.is_running = False
        self.active_tasks = {}

    async def start(self):
        """Schedulerni ishga tushirish"""
        if self.is_running:
            return
        self.is_running = True
        self.scheduler_task = asyncio.create_task(self.schedule_advertisements())
        logging.info("Advertisement handler started.")

    async def stop(self):
        """Schedulerni to'xtatish"""
        self.is_running = False
        if hasattr(self, "scheduler_task"):
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                logging.info("Advertisement handler stopped.")

    async def get_photo_access_hash(self, client, photo_id):
        """Rasmning `access_hash` ma'lumotlarini olish"""
        try:
            message = await client.get_messages(None, ids=photo_id)
            if message and message.media and isinstance(message.media.photo, InputPhoto):
                input_photo = message.media.photo
                return {
                    "id": input_photo.id,
                    "access_hash": input_photo.access_hash,
                    "file_reference": input_photo.file_reference
                }
            else:
                raise ValueError("Rasm topilmadi yoki noto'g'ri format!")
        except Exception as e:
            logging.error(f"Rasmni olishda xatolik: {str(e)}")
            return None

    async def send_advertisement(self, client, group_id, photo_data, text):
        """Rasm yoki matnni yuborish"""
        try:
            if photo_data:
                media = InputPhoto(
                    id=photo_data["id"],
                    access_hash=photo_data["access_hash"],
                    file_reference=photo_data["file_reference"]
                )
                await client.send_file(
                    group_id,
                    file=media,
                    caption=text,
                    parse_mode='html'
                )
            else:
                await client.send_message(
                    group_id,
                    text,
                    parse_mode='html'
                )
            logging.info(f"Reklama muvaffaqiyatli yuborildi: {group_id}")
        except Exception as e:
            logging.error(f"Reklamani yuborishda xatolik: {str(e)}")

    async def process_advertisement(self, ad):
        """Bitta reklamani qayta ishlash"""
        try:
            client_info = await db.get_client_for_advertisement(ad["created_by"])
            if not client_info:
                logging.error(f"No active client found for user {ad['created_by']}")
                return

            async with TelegramClient(
                StringSession(client_info["stringsession"]),
                int(client_info["api_id"]),
                client_info["api_hash"]
            ) as client:
                await client.connect()
                photo_data = None
                if ad["photo_id"]:
                    photo_data = await self.get_photo_access_hash(client, ad["photo_id"])

                for group_id in ad["group_ids"]:
                    await self.send_advertisement(client, group_id, photo_data, ad["text"])
                    await asyncio.sleep(2)  # Guruhlar orasida 2 soniya kutish
        except Exception as e:
            logging.error(f"Error processing advertisement {ad['id']}: {str(e)}")

    async def schedule_advertisements(self):
        """Reklamalarni rejalashtirish"""
        while self.is_running:
            try:
                current_time = asyncio.get_event_loop().time()
                ads = await self.get_active_advertisements()

                for ad in ads:
                    if await self.should_send_advertisement(ad, current_time):
                        task = asyncio.create_task(self.process_advertisement(ad))
                        self.active_tasks[ad["id"]] = task

                await asyncio.sleep(60)
                completed_tasks = [ad_id for ad_id, task in self.active_tasks.items() if task.done()]
                for ad_id in completed_tasks:
                    del self.active_tasks[ad_id]
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in scheduling loop: {str(e)}")
                await asyncio.sleep(60)

    async def should_send_advertisement(self, ad, current_time):
        """Reklamani yuborish kerakligini tekshirish"""
        last_sent = ad.get("last_sent")
        duration_minutes = ad["duration_minutes"]

        if not last_sent:
            return True

        elapsed_minutes = (current_time - last_sent).total_seconds() / 60
        return elapsed_minutes >= duration_minutes

    async def get_active_advertisements(self):
        """Faol reklamalarni olish"""
        query = """
        SELECT a.id, a.photo_id, a.text, a.duration_minutes, a.created_by, a.group_ids, 
               a.created_at, a.is_active, COALESCE(MAX(l.sent_at), a.created_at) as last_sent
        FROM Advertisements a
        LEFT JOIN AdvertisementLogs l ON a.id = l.ad_id
        WHERE a.is_active = TRUE
        GROUP BY a.id
        """
        try:
            return await db.execute(query, fetch=True)
        except Exception as e:
            logging.error(f"Error fetching advertisements: {str(e)}")
            return []

