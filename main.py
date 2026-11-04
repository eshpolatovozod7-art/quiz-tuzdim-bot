import asyncio
import logging
import os
import sys
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from database.db import init_db
from handlers import (
    common,
    quiz_create,
    quiz_play,
    export_handlers,
    inline,
    channel_handlers,
    daily_handlers,
    duel_handlers,
)
from services.scheduler_service import channel_scheduler_worker

# Loggingni sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def start_health_server(port: int) -> web.AppRunner:
    """Render kabi bulut platformalari (Web Service) uchun port tekshiruvi (Health Check)."""
    app = web.Application()

    async def handle_ping(request: web.Request) -> web.Response:
        return web.Response(text="Quiz Tuzdim Bot is running! 🚀\nStatus: Healthy", status=200)

    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health-check veb-serveri ishga tushdi: http://0.0.0.0:%d", port)
    return runner


async def start_keep_alive(app_url: str) -> None:
    """Render bepul tarifida botni avtomatik uyg'oq tutish (Self Keep-Alive)."""
    url = app_url.rstrip("/") + "/health"
    logger.info("Self keep-alive ishga tushirildi: %s", url)
    await asyncio.sleep(60)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    logger.debug("Keep-alive ping yuborildi, javob: %s", resp.status)
        except Exception as e:
            logger.debug("Keep-alive ping xatosi (muhim emas): %s", e)
        await asyncio.sleep(720)  # Har 12 daqiqada ping qilish (15 daqiqali limitdan oldin)


async def set_bot_commands(bot: Bot) -> None:
    """Bot buyruqlari menyusi."""
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish va asosiy menyu"),
        BotCommand(command="daily", description="Har kungi Kun Testi (Streak)"),
        BotCommand(command="duel", description="1 vs 1 Do'stona Viktorina Jangi"),
        BotCommand(command="poll", description="Guruhga test (so'rovnoma)larni tashlash"),
        BotCommand(command="top", description="Guruh reytingi va peshqadamlar jadvali"),
        BotCommand(command="excel", description="Guruh natijalarini Excel jadvalda olish"),
        BotCommand(command="help", description="Qo'llanma va yordam"),
        BotCommand(command="stats", description="Shaxsiy testlar statistikasi"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN aniqlanmadi! .env faylini tekshiring.")
        return

    logger.info("Ma'lumotlar bazasi ishga tushirilmoqda...")
    await init_db()

    web_runner = None
    keep_alive_task = None

    port_env = os.getenv("PORT")
    if port_env and port_env.isdigit():
        try:
            web_runner = await start_health_server(int(port_env))
        except Exception as web_err:
            logger.warning("Veb-serverni ishga tushirishda xatolik: %s", web_err)

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        keep_alive_task = asyncio.create_task(start_keep_alive(render_url))

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Routerlarni qo'shish (tartib muhim!)
    dp.include_router(common.router)
    dp.include_router(daily_handlers.router)
    dp.include_router(duel_handlers.router)
    dp.include_router(channel_handlers.router)
    dp.include_router(export_handlers.router)
    dp.include_router(quiz_play.router)
    dp.include_router(quiz_create.router)
    dp.include_router(inline.router)

    scheduler_task = None
    try:
        await set_bot_commands(bot)
        bot_info = await bot.get_me()
        logger.info("Bot muvaffaqiyatli ishga tushdi: @%s (%s)", bot_info.username, bot_info.first_name)

        scheduler_task = asyncio.create_task(channel_scheduler_worker(bot))

        # Eski kutilmagan yangilanishlarni tashlab yuborish
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        if scheduler_task:
            scheduler_task.cancel()
        if keep_alive_task:
            keep_alive_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
