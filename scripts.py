import asyncio
import os
import tempfile
import logging
from datetime import datetime
from telethon.sessions import StringSession
from telethon.sync import TelegramClient
import aiohttp
from loader import db, bot


class AdvertisementScheduler:
    def __init__(self):
        self.is_running = False
        self.active_tasks = {}

    async def start(self):
        """Start the advertisement scheduler"""
        if self.is_running:
            return

        self.is_running = True
        self.schedule_task = asyncio.create_task(self.schedule_advertisements())
        logging.info("Advertisement scheduler started.")

    async def stop(self):
        """Stop the advertisement scheduler"""
        self.is_running = False
        if self.schedule_task:
            self.schedule_task.cancel()
            try:
                await self.schedule_task
            except asyncio.CancelledError:
                logging.info("Advertisement scheduler stopped.")

    async def get_active_advertisements(self):
        """Get all active advertisements from database"""
        sql = """
        SELECT id, photo_id, text, duration_minutes, created_by, group_ids, created_at
        FROM Advertisements
        WHERE is_active = TRUE;
        """
        try:
            return await db.execute(sql, fetch=True)
        except Exception as e:
            logging.error(f"Error fetching advertisements: {str(e)}")
            return []

    async def send_advertisement(self, client, group_id, photo_id, text):
        """Send advertisement to a specific group"""
        if not photo_id:  # Agar photo_id yo'q bo'lsa
            try:
                await client.send_message(group_id, text)
                logging.info(f"Text advertisement sent to group {group_id}")
                return True
            except Exception as e:
                logging.error(f"Error sending text to group {group_id}: {str(e)}")
                return False

        temp_file = None
        try:
            file_info = await bot.get_file(photo_id)
            file_path = file_info.file_path

            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_path = temp_file.name
            temp_file.close()

            file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_path}"
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(temp_path, 'wb') as f:
                            f.write(content)

                        # Telethon orqali rasm yuborish
                        await client.send_file(
                            group_id,
                            temp_path,
                            caption=text,
                            force_document=False  # Rasmni file sifatida emas, rasm sifatida yuborish
                        )
                        logging.info(f"Photo advertisement sent to group {group_id}")
                        return True
                    else:
                        logging.error(f"Failed to download file: {response.status}")
                        return False

        except Exception as e:
            logging.error(f"Error sending advertisement to group {group_id}: {str(e)}")
            return False

        finally:
            if temp_file and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logging.error(f"Error deleting temporary file: {str(e)}")

    async def process_advertisement(self, ad):
        """Process single advertisement"""
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
                for group_id in ad['group_ids']:
                    success = await self.send_advertisement(
                        client,
                        group_id,
                        ad['photo_id'],
                        ad['text']
                    )
                    if success:
                        await db.log_advertisement_send(ad['id'], group_id)
                    await asyncio.sleep(2)  # Guruhlar orasida kutish

        except Exception as e:
            logging.error(f"Error processing advertisement {ad['id']}: {str(e)}")

    async def schedule_advertisements(self):
        """Main scheduling loop"""
        while self.is_running:
            try:
                current_time = datetime.now()
                ads = await self.get_active_advertisements()

                for ad in ads:
                    created_at = ad['created_at']
                    duration_minutes = ad['duration_minutes']

                    # Oxirgi yuborilgan vaqtdan beri o'tgan daqiqalar
                    elapsed_minutes = (current_time - created_at).total_seconds() / 60

                    # Agar belgilangan vaqt o'tgan bo'lsa
                    if elapsed_minutes >= duration_minutes:
                        await self.process_advertisement(ad)

                        # Yuborilgan vaqtni yangilash
                        await db.execute(
                            """
                            UPDATE Advertisements
                            SET created_at = CURRENT_TIMESTAMP
                            WHERE id = $1 AND is_active = TRUE
                            """,
                            ad['id'],
                            execute=True
                        )
                        logging.info(f"Advertisement {ad['id']} sent at {current_time}")

                # Har 30 sekundda tekshirish
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in schedule_advertisements: {str(e)}")
                await asyncio.sleep(30)  # Xatolik yuz berganda ham kutish