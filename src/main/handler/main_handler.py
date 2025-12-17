from aiogram import *
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram import Router

from main.handler.device_info_handler import devices_info
from main.handler.guarantee_handler import guarantee
from main.handler.promotion_handler import get_promotion
from main.handler.technical_department_handler import technical_support_department
from main.middleware.middleware import ChatActionMiddleware
from main.service.model.user_service import UserService
from main.utils import send_message_from_msg, send_message_from_call


###
###### Хендлер для работы с основными командами
####
##


router = Router()
router.message.middleware(ChatActionMiddleware())

user_service = UserService()


@router.message(Command('start'))
async def start(message: Message):
    """
    Метод запускает бота

    :param message: Сообщение от пользоваетля
    """

    await user_service.create_user(chat_id=message.chat.id,
                                   username=message.from_user.username,
                                   full_name=message.from_user.full_name)

    await send_message_from_msg(message=message,
                                text="Это Бот-помощник компании ТОП ШИН 24! Используя данного бота вы соглашаетесь на обработку персональных данных "
                                     "и на получение Email писем с выгодными предложениями.\n\n"
                                     "Для работы выберите команды из списка по кнопке 'Меню'\n\n"
                                     "Мои возможности:\n"
                                     "  🔹 Активировать гарантию 📑\n"
                                     "  🔹 Посмотреть информацию о своих устройствах 💻\n"
                                     "  🔹 Получить информацию о сервисном центре 🔧\n"
                                     "  🔹 Посмотреть актуальные акции и предложения 📉",
                                keyboard=ReplyKeyboardRemove())


@router.message(Command('guarantee'))
async def guarantee_main(message: Message, state: FSMContext):
    """
    Вызов метода инициализации гарантии

    :param state: Состояние
    :param message: Сообщение от пользователя
    """
    await guarantee(message, state)


@router.message(Command('promotion'))
async def promotion_main(message: Message):
    """
    Вызов метода работы с акциями

    :param message: Сообщение от пользователя
    """

    await get_promotion(message)


@router.message(Command('device_info'))
async def device_info_main(message: Message):
    """
    Вызов метода работы с информацией о устройствах клиента

    :param message: Сообщение от пользователя
    """

    await devices_info(message)


@router.message(Command('technical_support_department'))
async def technical_support_department_main(message: Message):
    """
    Вызов метода работы с сервисным центром

    :param message: Сообщение от пользователя
    """

    await technical_support_department(message)


@router.message(Command('support'))
async def support_command(message: Message):
    """
    Команда /support — выводит контакт техподдержки.
    """

    await send_message_from_msg(
        message=message,
        text="Техподдержка - @RackotXO "
    )


@router.callback_query(F.data.startswith('main_action_'))
async def cancel_action(call: CallbackQuery, state: FSMContext):
    """
    Метод отменяет текущее действие (отчищает заданное состояние)

    :param call: Текст кнопки
    :param state: Состояние
    """

    await state.clear()
    action_type = str(call.data.replace('main_action_', ''))

    match action_type:
        case "cancel":
            await send_message_from_call(call=call,
                                         text="Действие отменено")
        case "refuse":
            await send_message_from_call(call=call,
                                         text="Благодарим за Ваш выбор")
