from aiogram import Router
from aiogram.enums import ChatType

from filters import ChatTypeFilter



def setup_routers() -> Router:
    from .users import admin, start, add_client, all_clients, add_advertisment, all_advertisements, remove_accounts, reset_bot
    from .errors import error_handler

    # Asosiy router yaratish
    router = Router(name="main_router")

    # Har bir routerni alohida e'lon qilish
    routers = [
        admin.router,
        start.router,
        add_client.router,
        all_clients.router,
        add_advertisment.router,
        error_handler.router,
        all_advertisements.router,
        remove_accounts.router,
        reset_bot.router
    ]

    # Filter qo'shish
    start.router.message.filter(ChatTypeFilter(chat_types=[ChatType.PRIVATE]))

    # Routerlarni birma-bir qo'shish
    for r in routers:
        if not isinstance(r, Router):
            raise ValueError(f"Router expected, got {type(r)}")
        router.include_router(r)

    return router