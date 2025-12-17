from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import Message, TelegramObject
from aiogram.utils.chat_action import ChatActionSender

from main.config.log_config import logger


class ChatActionMiddleware(BaseMiddleware):
    # Показывает пользователю анимацию "...печатает" при получении сообщения и до отправки ответа

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:

        async with ChatActionSender.typing(event.chat.id, event.bot):
            return await handler(event, data)


class ErrorLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict
    ):
        try:
            return await handler(event, data)
        except Exception as e:
            logger.exception(f"Ошибка при обработке события {type(event)}: {e}", extra={"service": "general"})