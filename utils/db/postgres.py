from typing import Union
import ssl
import asyncpg
from asyncpg import Connection
from asyncpg.pool import Pool
from aiogram.client.session.middlewares.request_logging import logger
from data import config



class Database:
    def __init__(self):
        self.pool: Union[Pool, None] = None

    async def create(self):
        self.pool = await asyncpg.create_pool(
            dsn=config.DATABASE_URL,
            ssl=self.get_ssl_context()
        )

    def get_ssl_context(self):
        context = ssl.create_default_context(cafile=config.SSL_CERT_FILE)
        return context

    async def execute(
        self,
        command,
        *args,
        fetch: bool = False,
        fetchval: bool = False,
        fetchrow: bool = False,
        execute: bool = False,
    ):
        
        async with self.pool.acquire() as connection:
            connection: Connection
            async with connection.transaction():
                if fetch:
                    result = await connection.fetch(command, *args)
                elif fetchval:
                    result = await connection.fetchval(command, *args)
                elif fetchrow:
                    result = await connection.fetchrow(command, *args)
                elif execute:
                    result = await connection.execute(command, *args)
            return result

    async def create_table_advertisement(self):
        sql = """
        CREATE TABLE IF NOT EXISTS Advertisements (
            id SERIAL PRIMARY KEY,
            photo_id TEXT NOT NULL,
            text TEXT NOT NULL,
            duration_minutes INT NOT NULL,
            created_by BIGINT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            group_ids BIGINT[] NOT NULL
        );
        """
        await self.execute(sql, execute=True)


    async def create_table_clients(self):
        sql = """
        CREATE TABLE IF NOT EXISTS Clients (
            id SERIAL PRIMARY KEY,
            api_id VARCHAR(255),
            api_hash TEXT,
            phone VARCHAR(100),
            stringsession TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            is_banned BOOlEAN DEFAULT FALSE
        );
        """
        await self.execute(sql, execute=True)
        
    async def create_table_advertisement_logs(self):
        sql = """
        CREATE TABLE IF NOT EXISTS AdvertisementLogs (
            id SERIAL PRIMARY KEY,
            ad_id INT REFERENCES Advertisements(id),
            group_id BIGINT NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        await self.execute(sql, execute=True)

    async def create_table_users(self):
        sql = """
        CREATE TABLE IF NOT EXISTS Users (
            id SERIAL PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            username VARCHAR(255) NULL,
            telegram_id BIGINT NOT NULL UNIQUE,
            active_client_session INT,
            FOREIGN KEY (active_client_session) REFERENCES Clients(id) ON DELETE SET NULL
        );
        """
        await self.execute(sql, execute=True)

    @staticmethod
    def format_args(sql, parameters: dict):
        sql += " AND ".join(
            [f"{item} = ${num}" for num, item in enumerate(parameters.keys(), start=1)]
        )
        return sql, tuple(parameters.values())

    async def add_advertisement(self, photo_id, text, duration_minutes, created_by, group_ids):
        """
        Add a new advertisement to the Advertisements table.

        :param photo_id: The photo file ID.
        :param text: The advertisement text.
        :param duration_minutes: The duration of the advertisement in minutes.
        :param created_by: The Telegram ID of the user who created the advertisement.
        :return: The inserted advertisement record.
        """
        sql = """
        INSERT INTO advertisements (photo_id, text, duration_minutes, created_by, group_ids)
        VALUES ($1, $2, $3, $4, $5) RETURNING *;
        """
        return await self.execute(sql, photo_id, text, duration_minutes, created_by, group_ids, fetchrow=True)

    async def add_user(self, full_name, username, telegram_id):
        sql = "INSERT INTO users (full_name, username, telegram_id) VALUES($1, $2, $3) returning *"
        return await self.execute(sql, full_name, username, telegram_id, fetchrow=True)

    async def add_client(self, api_id, api_hash, phone, stringsession):
        sql = "INSERT INTO clients (api_id, api_hash, phone, stringsession) VALUES($1, $2, $3, $4) returning *"
        return await self.execute(sql, api_id, api_hash, phone, stringsession, fetchrow=True)

    async def deactivate_advertisement(self, ad_id):
        """
        Reklamani nofaol holatga o'tkazish.

        :param ad_id: Reklama ID-si
        :return: Hech narsa qaytarmaydi
        """
        sql = """
        UPDATE Advertisements
        SET is_active = FALSE
        WHERE id = $1;
        """
        await self.execute(sql, ad_id)

    async def get_active_advertisements(self):
        try:
            sql = """
            SELECT id, photo_id, text, duration_minutes, created_by, group_ids, created_at
            FROM Advertisements
            WHERE is_active = TRUE;
            """
            return await self.execute(sql, fetch=True)
        except Exception as e:
            logger.error(f"Error in get_active_advertisements: {str(e)}")
            return []


    async def log_advertisement_send(self, ad_id: int, group_id: int):
        """Yuborilgan reklamani qayd qilish"""
        sql = """
        INSERT INTO AdvertisementLogs (ad_id, group_id) 
        VALUES ($1, $2)
        ON CONFLICT (ad_id, group_id) 
        DO UPDATE SET sent_at = CURRENT_TIMESTAMP;
        """
        await self.execute(sql, ad_id, group_id, execute=True)

    async def mark_advertisement_completed(self, ad_id: int):
        """Reklamani tugatilgan deb belgilash"""
        sql = """
        UPDATE Advertisements 
        SET duration_minutes = 0 
        WHERE id = $1
        """
        await self.execute(sql, ad_id, execute=True)

    async def get_client_by_user_id(self, user_id: int):
        """Foydalanuvchining aktiv klientini olish"""
        sql = """
        SELECT c.* FROM Clients c
        JOIN Users u ON u.active_client_session = c.id
        WHERE u.telegram_id = $1 
        AND c.is_active = TRUE 
        AND c.is_banned = FALSE;
        """
        return await self.execute(sql, user_id, fetchrow=True)

    async def get_client_for_advertisement(self, created_by: int):
        """Get client info for advertisement sending"""
        sql = """
        SELECT c.api_id, c.api_hash, c.stringsession 
        FROM Clients c
        JOIN Users u ON u.active_client_session = c.id
        WHERE u.telegram_id = $1 
        AND c.is_active = TRUE 
        AND c.is_banned = FALSE;
        """
        return await self.execute(sql, created_by, fetchrow=True)

    async def get_active_client(self, telegram_id: int):
        """
        Retrieve the active client session for a user based on their telegram_id.

        :param telegram_id: The Telegram ID of the user.
        :return: The active client session ID or None if not set.
        """
        sql = """
        SELECT active_client_session 
        FROM Users 
        WHERE telegram_id = $1;
        """
        result = await self.execute(sql, telegram_id, fetchrow=True)
        return result["active_client_session"] if result else None



    async def switch_active_client(self, user_id: int, client_id: int):
        """
        Switch the active client session for a user.

        :param user_id: The ID of the user in the Users table.
        :param client_id: The ID of the client in the Clients table to set as active.
        """
        sql = """
        UPDATE Users
        SET active_client_session = $1
        WHERE id = $2;
        """
        await self.execute(sql, (client_id, user_id), execute=True)

    async def get_all_clients(self):
        sql = "SELECT * FROM Clients"
        return await self.execute(sql, fetch=True)

    async def select_all_users(self):
        sql = "SELECT * FROM Users"
        return await self.execute(sql, fetch=True)

    async def select_user(self, **kwargs):
        sql = "SELECT * FROM Users WHERE "
        sql, parameters = self.format_args(sql, parameters=kwargs)
        return await self.execute(sql, *parameters, fetchrow=True)

    async def count_users(self):
        sql = "SELECT COUNT(*) FROM Users"
        return await self.execute(sql, fetchval=True)

    async def count_clients(self):
        sql = "SELECT COUNT(*) FROM Clients"
        return await self.execute(sql, fetchval=True)

    async def update_user_username(self, username, telegram_id):
        sql = "UPDATE Users SET username=$1 WHERE telegram_id=$2"
        return await self.execute(sql, username, telegram_id, execute=True)

    async def delete_users(self):
        await self.execute("DELETE FROM Users WHERE TRUE", execute=True)

    async def drop_users(self):
        await self.execute("DROP TABLE Users", execute=True)
