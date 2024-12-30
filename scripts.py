import asyncio
import logging
from datetime import datetime
from telethon.sessions import StringSession
from telethon.sync import TelegramClient
from loader import db
import json


class AdvertisementScheduler:
    def __init__(self):
        self.is_running = False
        self.active_tasks = {}

    async def start(self):
        """Schedulerni ishga tushirish"""
        if self.is_running:
            return

        self.is_running = True
        self.schedule_task = asyncio.create_task(self.schedule_advertisements())
        logging.info("Advertisement scheduler started.")

    async def stop(self):
        """Schedulerni to'xtatish"""
        self.is_running = False
        if hasattr(self, 'schedule_task'):
            self.schedule_task.cancel()
            try:
                await self.schedule_task
            except asyncio.CancelledError:
                logging.info("Advertisement scheduler stopped.")

    async def get_active_advertisements(self):
        """Aktiv reklamalarni bazadan olish"""
        sql = """
        SELECT a.id, a.photo_id, a.text, a.duration_minutes, a.created_by, 
               a.group_ids, a.created_at, a.is_active,
               COALESCE(MAX(l.sent_at), a.created_at) as last_sent
        FROM Advertisements a
        LEFT JOIN AdvertisementLogs l ON a.id = l.ad_id
        WHERE a.is_active = TRUE
        GROUP BY a.id
        """
        try:
            return await db.execute(sql, fetch=True)
        except Exception as e:
            logging.error(f"Error fetching advertisements: {str(e)}")
            return []

    async def send_advertisement(self, client, group_id, photo_id, text):
        """Reklamani yuborish"""
        try:
            # O'zbek harflarini to'g'rilash
            text = text.replace('&#x27;', "'").replace('&quot;', '"')

            if photo_id:
                try:
                    # photo_id dan rasmni yuborish
                    await client.send_file(
                        entity=group_id,
                        file=photo_id,
                        caption=text,
                        parse_mode='html'
                    )
                except Exception as e:
                    logging.error(f"Invalid photo_id or error sending file: {photo_id}, {str(e)}")
                    await client.send_message(
                        group_id,
                        text,
                        parse_mode='html'
                    )
            else:
                # Faqat matnni yuborish
                await client.send_message(
                    group_id,
                    text,
                    parse_mode='html'
                )

            logging.info(f"Advertisement sent to group {group_id}")
            return True

        except Exception as e:
            logging.error(f"Error sending advertisement to group {group_id}: {str(e)}")
            return False

    async def should_send_advertisement(self, ad, current_time):
        """Reklamani yuborish vaqti kelganligini tekshirish"""
        last_sent = ad['last_sent']
        if isinstance(last_sent, str):  # Agar string bo'lsa, uni datetime obyektiga aylantirish
            last_sent = datetime.fromisoformat(last_sent)

        duration_minutes = ad['duration_minutes']
        if not last_sent:
            return True

        # Oxirgi yuborilgan vaqtdan beri o'tgan daqiqalar
        time_since_last_send = (current_time - last_sent).total_seconds() / 60
        return time_since_last_send >= float(duration_minutes)

    async def process_advertisement(self, ad):
        """Bitta reklamani qayta ishlash"""
        try:
            client_info = await db.get_client_for_advertisement(ad['created_by'])

            if not client_info:
                logging.error(f"No active client found for user {ad['created_by']}")
                return

            async with TelegramClient(
                    StringSession(client_info['stringsession']),
                    int(client_info['api_id']),
                    client_info['api_hash']
            ) as client:
                await client.connect()
                group_ids = json.loads(ad['group_ids']) if isinstance(ad['group_ids'], str) else ad['group_ids']

                tasks = [
                    asyncio.create_task(self.send_advertisement(client, group_id, ad['photo_id'], ad['text']))
                    for group_id in group_ids
                ]
                results = await asyncio.gather(*tasks)

                # Log yuborilganlar
                for group_id, success in zip(group_ids, results):
                    if success:
                        await db.log_advertisement_send(ad['id'], group_id)

        except Exception as e:
            logging.error(f"Error processing advertisement {ad['id']}: {str(e)}")

    async def schedule_advertisements(self):
        """Asosiy scheduling loop"""
        while self.is_running:
            try:
                current_time = datetime.now()
                ads = await self.get_active_advertisements()

                for ad in ads:
                    if await self.should_send_advertisement(ad, current_time):
                        # Reklamani alohida task sifatida ishga tushirish
                        task = asyncio.create_task(self.process_advertisement(ad))
                        self.active_tasks[ad['id']] = task

                # Har 60 sekundda yangi reklamalarni tekshirish
                await asyncio.sleep(60)

                # Tugallangan tasklarni tozalash
                completed_tasks = [ad_id for ad_id, task in self.active_tasks.items() if task.done() or task.cancelled()]
                for ad_id in completed_tasks:
                    del self.active_tasks[ad_id]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in schedule_advertisements: {str(e)}")
                await asyncio.sleep(60)
