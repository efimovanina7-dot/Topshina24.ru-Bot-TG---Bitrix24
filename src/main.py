import asyncio
import sys
import threading
from pathlib import Path
from aiogram import *
from aiogram.fsm.storage.memory import MemoryStorage


# Добавляем папку src в sys.path
project_root = Path(__file__).resolve().parent  # Получаем путь к корню проекта
src_folder = project_root / 'src'  # Путь к папке src
sys.path.append(str(src_folder))  # Добавляем путь в sys.path

from main.config.bot_config import scheduler
from main.config.db_config import create_tables
from main.config.log_config import asyncio_exception_handler
from main.middleware.middleware import ErrorLoggingMiddleware
from main.handler.main_handler import router as main_router
from main.handler.administration_handler import router as admin_router
from main.handler.guarantee_handler import router as guarantee_router
from main.handler.promotion_handler import router as promotion_router
from main.handler.device_info_handler import router as device_info_router
from main.handler.technical_department_handler import router as technical_department_router
from main.handler.broadcast_handler import router as broadcast_router
from main.service.integration.notifications_service import setup_scheduled_jobs
from main.utils import *


async def run_bot():
    """
    Метод запуска бота
    """

    dispatcher = Dispatcher(storage=MemoryStorage())

    # Перехват возможных ошибок
    dispatcher.message.middleware(ErrorLoggingMiddleware())
    dispatcher.callback_query.middleware(ErrorLoggingMiddleware())
    dispatcher.errors.middleware(ErrorLoggingMiddleware())

    # Подключение роутеров
    dispatcher.include_routers(main_router,
                               admin_router,
                               broadcast_router,
                               guarantee_router,
                               device_info_router,
                               promotion_router,
                               technical_department_router)

    # Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    await set_bot_commands(bot)
    await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())


async def start():
    """
    Метод запуска приложения
    """

    # Создание таблиц
    await create_tables()

    # Настройка и запуск задач APScheduler
    setup_scheduled_jobs()
    scheduler.start()

    print("Бот запущен")
    logger.info("Бот запущен", extra={"service": "main"})

    await run_bot()


if __name__ == '__main__':
    try:

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.set_exception_handler(asyncio_exception_handler)
        loop.run_until_complete(start())

    # except ConnectionError as e:
    #     logger.error(f"Ошибка соединени: {e}", extra={"service": "main"})
    # except Exception as r:
    #     logger.error(f"Непридвиденная ошибка: {r}", extra={"service": "main"})
    finally:
        logger.info("Бот завершил работу", extra={"service": "main"})
        print("Бот завершил работу")

