from datetime import datetime

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram import Router, F
from aiogram.types import FSInputFile
import os

from main.dto.guarantee_request_dto import GuaranteeCreateBitrix24RequestDTO
from main.dto.guarantee_response_dto import GuaranteeResponseDTO
from main.keyboard.guarantee_keyboard import *
from main.enum.guarantee_enum import GuaranteeInformationEnum
from main.keyboard.main_menu_keyboard import CheckingEmailCall, get_checking_email_keyboard
from main.middleware.middleware import ChatActionMiddleware
from main.model.guarantee_base import GuaranteeBase
from main.service.model.device_service import DeviceService
from main.service.model.guarantee_service import GuaranteeService
from main.service.model.user_service import UserService
from main.service.handler.guarantee_handler_service import *
from main.service.integration.mail_service import *
from main.service.integration.pdf_service import generate_certificate_pdf
from main.config.bot_config import bot
from main.state.state import RegistrationAndActivateGuaranteeState, UpdateUserAndDeviceDataState, \
    ActivateGuaranteeState, UpdateUserDataState
from main.utils import *



###### Хендлер для работы с Гарантийным планом
####
##


router = Router()
router.message.middleware(ChatActionMiddleware())

user_service = UserService()
guarantee_service = GuaranteeService()
device_service = DeviceService()


###
###### Сбор данных пользователя
####
##


#@router.message(Command('guarantee'))
async def guarantee(message: Message, state: FSMContext):
    """
    Метод инициализирует активацию гарантии

    :param state: Состояние
    :param message: Сообщение от пользователя
    """

    user:UserBase = await user_service.create_user(chat_id=message.chat.id,
                                                   username=message.from_user.username,
                                                   full_name=message.from_user.full_name)

    # Проверяем заполненность профиля
    if await user_service.is_completed_profile(user):
        # Если профиль пользователя заполнен - запрашиваем данные по устройству

        user_dto = UserResponseDTO(user)
        await send_check_user_data_message(message, user)

    else:
        # Иначе начинаем регистрацию пользователя

        await send_message_from_msg(message=message,
                                    text="Для активации гарантии вам необходимо уточнить несколько параметров:\n"
                                         "  🔻 _Согласие на обработку ПДн_\n"
                                         "  🔻 _Согласие на маркетинговые коммуникации_\n"
                                         "  🔻 _Фамилия_\n"
                                         "  🔻 _Имя_\n"
                                         "  🔻 _Номер телефона_\n"
                                         "  🔻 _Email_\n"
                                         "  🔻 _Город/регион_\n"
                                         "  🔻 _Источник заказа_\n"
                                         "  🔻 _Серийный номер устройства_\n"
                                         "  🔻 _Дата покупки устройства_"
                                    )

        await start_registration_guarantee(message, state)


@router.callback_query(F.data.startswith('user_data_approve'))
async def prepare_to_serial_number(call: CallbackQuery, state: FSMContext):
    """
    Метод запрашивает серийный номер устройства

    :param state: Состояние
    :param message: Сообщение от пользователя
    """

    await send_message_from_call(call=call,
                                text="Введите _серийный номер_ вашего устройства.\n"
                                     "(Серийный номер должен содержать набор цифр без пробелов)",
                                keyboard=cancel_action_keyboard)
    await state.set_state(ActivateGuaranteeState.set_serial_number)


@router.message(ActivateGuaranteeState.set_serial_number)
async def set_serial_number_and_prepare_to_purchase_date(message: Message, state: FSMContext):
    """
    Метод принимает серийный номер от пользователя и запрашивает дату покупки устройства.

    :param message: Сообщение от пользователя
    :param state: Состояние
    """

    try:
        serial_number = str(message.text)
        await is_correct_format_serial_number(serial_number)

        # Поиск устройства и сохранение его в системе
        device = await device_service.get_device_or_identify_and_create(serial_number=serial_number,
                                                                        user_id=message.from_user.id)

        await state.update_data(set_serial_number=serial_number)
        await send_message_from_msg(message=message,
                                    text="Введите _дату покупки_ вашего устройства, указанную в чеке.\n"
                                         "(Дата должна быть в формате: ДД.ММ.ГГГГ)\n\n"
                                         "*Начало гарантийного периода типа 'Стандарт' начинается с даты покупки из чека!* "
                                         "*Сохраните чек, он понадобиться в случае обращения в Сервисный центр.*",
                                    keyboard=cancel_action_keyboard)
        await state.set_state(ActivateGuaranteeState.set_purchase_date)

    except (IncorrectSerialNumberException, NotFoundDeviceBySerialNumberException, DeviceIsRegisteredException) as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(ActivateGuaranteeState.set_serial_number)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(ActivateGuaranteeState.set_purchase_date)
async def set_serial_number_and_update_data(message: Message, state: FSMContext):
    """
    Метод принимает дату покупки устройства от пользователя и сохраняет данные.

    :param message: Сообщение пользователя
    :param state: Состояние
    """

    try:
        purchase_date = str(message.text)
        await is_correct_format_date(purchase_date)
        await is_correct_period_date(purchase_date)

        purchase_date = datetime.strptime(purchase_date, "%d.%m.%Y").date()

        state_dict = await state.get_data()

        # Обновляем информацию по устройству
        device = await device_service.get_device_by_serial_number_and_user_id(serial_number= state_dict["set_serial_number"],
                                                                              user_id=message.from_user.id)
        device.purchase_date = purchase_date

        device = await device_service.update_device(device)
        user = await user_service.get_user(chat_id=message.chat.id)

        await state.clear()

        await send_check_user_and_device_data_message(message, user, device)

    except (IncorrectDateOfPurchaseException, IncorrectPeriodDateException) as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(ActivateGuaranteeState.set_purchase_date)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.callback_query(F.data.startswith('user_data_update'))
async def update_user_data(call: CallbackQuery):
    """
    Метод предоставляет выбор параметров для изменения

    :param call: Вызов кнопки
    """

    await delete_previous_message_and_send_new_from_call(call=call,
                                                         text="Что хотите изменить?",
                                                         keyboard=update_user_data_keyboard)


@router.callback_query(F.data.startswith('update_user_data_'))
async def choice_user_data(call: CallbackQuery, state: FSMContext):
    """
    Метод запрашивает новые данные по выбранному параметру

    :param call: Текст кнопки
    :param state: Состояние
    """

    msg = ""
    new_state = None

    await state.clear()
    action_type = str(call.data.replace('update_user_data_', ''))


    match action_type:
        case "name":
            new_state = UpdateUserDataState.name
            msg = "ваше _имя_"

        case "surname":
            new_state = UpdateUserDataState.surname
            msg = "вашу _фамилию_"

        case "phone":
            new_state = UpdateUserDataState.phone
            msg = ("ваш _номер телефона_ .\n"
                   "(Номер должен начинаться с +7, без пробелов и спец символов, и содержать 11 цифр)")

        case "email":
            new_state = UpdateUserDataState.email
            msg = ("ваш _Email_ .\n"
                   "(Email должен быть в формате: test@test.test)")

    await delete_previous_message_and_send_new_from_call(call=call,
                                                         text="Введите " + msg,
                                                         keyboard=cancel_action_keyboard)

    await state.set_state(new_state)


@router.message(UpdateUserDataState.name)
async def set_name_and_update(message: Message, state: FSMContext):
    """
    Метод принимает на вход обновленное имя и сохраняет в БД

    :param message: Сообщение пользователя
    :param state: Состояние
    """
    try:
        name = str(message.text)
        await is_correct_format_name(name)

        user = await user_service.set_name(chat_id=message.chat.id,
                                           name=name)

        await send_check_user_data_message(message, user)

        await state.clear()

    except IncorrectNameException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserDataState.name)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserDataState.surname)
async def set_surname_and_update(message: Message, state: FSMContext):
    """
    Метод принимает на вход обновленную фамилию и сохраняет в БД

    :param message: Сообщение пользователя
    :param state: Состояние
    """
    try:
        surname = str(message.text)
        await is_correct_format_name(surname)

        user = await user_service.set_surname(chat_id=surname,
                                              surname=surname)

        await send_check_user_data_message(message, user)

        await state.clear()
    except IncorrectNameException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserDataState.surname)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserDataState.phone)
async def set_phone_and_update(message: Message, state: FSMContext):
    """
    Метод принимает на вход обновленный телефон и сохраняет в БД

    :param message: Сообщение пользователя
    :param state: Состояние
    """
    try:
        phone = str(message.text)

        await is_correct_format_phone(phone)

        user = await user_service.set_phone(chat_id=message.chat.id,
                                            phone=phone)

        await send_check_user_data_message(message, user)

        await state.clear()

    except IncorrectPhoneException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserDataState.phone)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserDataState.email)
async def set_email_and_prepare_to_checking_number_for_update(message: Message, state: FSMContext):
    """
    Метод принимает на вход обновленный email пользователя, отправляет письмо с проверочным кодом и запрашивает его

    :param message: Сообщение пользователя
    :param state: Состояние
    """
    try:
        email = str(message.text)
        valid_email = await is_correct_format_email(email)
        await state.update_data(email=valid_email)

        checking_code = await send_checking_mail(valid_email)
        await state.update_data(checking_code=checking_code)

        await send_message_from_msg(message=message,
                                    text=f"На указанный электронный адрес {valid_email} было отправлено письмо с кодом подтверждения.\n"
                                         f"Если письмо не пришло, проверьте папку спам.\n\n"
                                         f"Пожалуйста введите код подтверждения из письма:",
                                    keyboard=await get_checking_email_keyboard(state="UpdateUserDataState"))

        await state.set_state(UpdateUserDataState.checking_code)

    except IncorrectEmailException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserDataState.email)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserDataState.checking_code)
async def set_checking_number_and_update_email(message: Message, state: FSMContext):
    """
    Метод принимает проверочный код и сохранет обновленный email

    :param message: Сообщение от пользователя
    :param state: Состояние
    """
    try:
        state_dict = await state.get_data()

        checking_code_from_user = str(message.text)
        checking_code = state_dict["checking_code"]
        email = state_dict["email"]

        await is_correct_checking_email_code(code_from_user=checking_code_from_user,
                                             checking_code=checking_code)

        user = await user_service.set_email(chat_id=message.chat.id,
                                            email=email)

        await send_check_user_data_message(message, user)

        await state.clear()


    except (IncorrectCheckingEmailCodeException, WrongCheckingEmailCodeException) as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserDataState.checking_code)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


###
###### Регистрация пользователя
####
##


@router.message(RegistrationAndActivateGuaranteeState.begin_registration)
async def start_registration_guarantee(message: Message, state: FSMContext):
    """
    Метод начинает регистрацию пользователя и запрашивает согласие на обработку ПДн

    :param message: Сообщение от пользователя
    :param state: Состояние
    """

    await send_message_from_msg(message=message,
                                text="📋 *Согласие на обработку персональных данных*\n\n"
                                     "Для продолжения необходимо дать согласие на обработку персональных данных.\n\n"
                                     "Нажимая кнопку «Согласен», вы подтверждаете своё согласие на обработку "
                                     "персональных данных в соответствии с Федеральным законом №152-ФЗ «О персональных данных».",
                                keyboard=pd_consent_keyboard)
    await state.set_state(RegistrationAndActivateGuaranteeState.pd_consent)


@router.callback_query(RegistrationAndActivateGuaranteeState.pd_consent, F.data == "pd_consent_agree")
async def pd_consent_agree_and_prepare_to_marketing(call: CallbackQuery, state: FSMContext):
    """
    Метод принимает согласие на ПДн и запрашивает согласие на маркетинг

    :param call: CallbackQuery
    :param state: Состояние
    """

    # Сохраняем согласие на ПДн
    await user_service.set_pd_consent(call.message.chat.id)

    await send_message_from_call(call=call,
                                text="📢 *Согласие на маркетинговые коммуникации*\n\n"
                                     "Для получения информации об акциях, специальных предложениях и новостях "
                                     "компании по email, SMS, мессенджерам и телефону, нажмите кнопку «Согласен».",
                                keyboard=marketing_consent_keyboard)
    await state.set_state(RegistrationAndActivateGuaranteeState.marketing_consent)


@router.callback_query(RegistrationAndActivateGuaranteeState.marketing_consent, F.data == "marketing_consent_agree")
async def marketing_consent_agree_and_prepare_to_surname(call: CallbackQuery, state: FSMContext):
    """
    Метод принимает согласие на маркетинг и запрашивает фамилию

    :param call: CallbackQuery
    :param state: Состояние
    """

    # Сохраняем согласие на маркетинг
    await user_service.set_marketing_consent(call.message.chat.id)

    await send_message_from_call(call=call,
                                text="✅ Спасибо! Теперь заполним ваши данные.\n\n"
                                     "Введите вашу _фамилию_",
                                keyboard=cancel_action_keyboard)
    await state.set_state(RegistrationAndActivateGuaranteeState.set_surname)


@router.message(RegistrationAndActivateGuaranteeState.set_surname)
async def set_surname_and_prepare_to_name(message: Message, state: FSMContext):
    """
    Метод принимает фамилию пользователя и запрашивает имя

    :param message: Сообщение от пользователя
    :param state: Состояние
    """
    try:
        surname = str(message.text)
        await is_correct_format_name(surname)
        await state.update_data(set_surname=surname)
        await send_message_from_msg(message=message,
                                    text="Введите ваше _имя_ ",
                                    keyboard=cancel_action_keyboard)

        await state.set_state(RegistrationAndActivateGuaranteeState.set_name)

    except IncorrectNameException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_surname)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(RegistrationAndActivateGuaranteeState.set_name)
async def set_name_and_prepare_to_phone(message: Message, state: FSMContext):
    """
    Метод принимает имя пользователя и запрашивает номер телефона

    :param message: Сообщение от пользователя
    :param state: Состояние
    """
    try:
        name = str(message.text)
        await is_correct_format_name(name)
        await state.update_data(set_name=name)
        await send_message_from_msg(message=message,
                                    text="Введите ваш _номер телефона_ .\n"
                                         "(Номер должен начинаться с +7, без пробелов и спец символов, и содержать 11 цифр)",
                                    keyboard=cancel_action_keyboard)

        await state.set_state(RegistrationAndActivateGuaranteeState.set_phone)

    except IncorrectNameException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_name)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(RegistrationAndActivateGuaranteeState.set_phone)
async def set_phone_and_prepare_to_email(message: Message, state: FSMContext):
    """
    Метод принимает номер телефона пользователя и запрашивает Email

    :param message: Сообщение от пользователя
    :param state: Состояние
    """

    try:
        phone = str(message.text)
        await is_correct_format_phone(phone)
        await state.update_data(set_phone=phone)
        await send_message_from_msg(message=message,
                                    text="Введите ваш _Email_ .\n"
                                         "(Email должен быть в формате: test@test.test)",
                                    keyboard=cancel_action_keyboard)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_email)
    except IncorrectPhoneException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_phone)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(RegistrationAndActivateGuaranteeState.set_email)
async def set_email_and_prepare_to_checking_number(message: Message, state: FSMContext):
    """
    Метод принимает Email пользователя, отправляет письмо с проверочным кодом и запрашивает его

    :param message: Сообщение от пользователя
    :param state: Состояние
    """

    try:
        email = str(message.text)
        valid_email = await is_correct_format_email(email)
        await state.update_data(set_email=valid_email)

        checking_code = await send_checking_mail(valid_email)
        await state.update_data(set_checking_code=checking_code)

        await send_message_from_msg(message=message,
                                    text=f"На указанный электронный адрес {valid_email} было отправлено письмо с кодом подтверждения.\n"
                                         f"Если письмо не пришло, проверьте папку спам.\n\n"
                                         f"Пожалуйста введите код подтверждения из письма:",
                                    keyboard=await get_checking_email_keyboard(state="RegistrationAndActivateGuaranteeState"))

        await state.set_state(RegistrationAndActivateGuaranteeState.set_checking_code)
    except IncorrectEmailException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_email)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(RegistrationAndActivateGuaranteeState.set_checking_code)
async def set_checking_number_and_prepare_to_city(message: Message, state: FSMContext):
    """
    Метод принимает проверочный код от пользователя и запрашивает город

    :param message: Сообщение от пользователя
    :param state: Состояние
    """

    try:
        state_dict = await state.get_data()

        checking_code_from_user = str(message.text)
        checking_code = state_dict["set_checking_code"]

        await is_correct_checking_email_code(code_from_user=checking_code_from_user,
                                             checking_code=checking_code)

        await send_message_from_msg(message=message,
                                    text="🏙 Введите ваш _город или регион_ проживания:",
                                    keyboard=cancel_action_keyboard)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_city)
    except (IncorrectCheckingEmailCodeException, WrongCheckingEmailCodeException) as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_checking_code)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(RegistrationAndActivateGuaranteeState.set_city)
async def set_city_and_prepare_to_order_source(message: Message, state: FSMContext):
    """
    Метод принимает город и запрашивает источник заказа

    :param message: Сообщение от пользователя
    :param state: Состояние
    """

    try:
        city = str(message.text).strip()
        if len(city) < 2:
            await send_message_from_msg(message=message,
                                        text="❌ Название города слишком короткое. Введите корректный город:")
            await state.set_state(RegistrationAndActivateGuaranteeState.set_city)
            return

        await state.update_data(set_city=city)

        await send_message_from_msg(message=message,
                                    text="🛒 Выберите _источник заказа_ (где вы приобрели товар):",
                                    keyboard=order_source_keyboard)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_order_source)

    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.callback_query(RegistrationAndActivateGuaranteeState.set_order_source, F.data.startswith("order_source_"))
async def set_order_source_and_prepare_to_serial_number(call: CallbackQuery, state: FSMContext):
    """
    Метод принимает источник заказа и запрашивает серийный номер

    :param call: CallbackQuery
    :param state: Состояние
    """

    try:
        source_map = {
            "order_source_ozon": "Ozon",
            "order_source_wb": "Wildberries",
            "order_source_ym": "Яндекс Маркет",
            "order_source_avito": "Avito",
            "order_source_retail": "Розница"
        }

        order_source = source_map.get(call.data, "Неизвестно")
        await state.update_data(set_order_source=order_source)

        await send_message_from_call(call=call,
                                    text="Введите _серийный номер_ вашего устройства.\n"
                                         "(Серийный номер должен содержать набор цифр без пробелов)",
                                    keyboard=cancel_action_keyboard)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_serial_number)

    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_call(call=call,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(RegistrationAndActivateGuaranteeState.set_serial_number)
async def set_serial_number_and_prepare_to_purchase_date_in_registration(message: Message, state: FSMContext):
    """
    Метод принимает серийный номер от пользователя и запрашивает дату покупки устройства.

    :param message: Сообщение от пользователя
    :param state: Состояние
    """

    try:
        serial_number = str(message.text)
        await is_correct_format_serial_number(serial_number)

        # Поиск устройства и сохранение его в системе
        device = await device_service.get_device_or_identify_and_create(serial_number=serial_number,
                                                                        user_id=message.from_user.id)

        await state.update_data(set_serial_number=serial_number)
        await send_message_from_msg(message=message,
                                    text="Введите _дату покупки_ вашего устройства, указанную в чеке.\n"
                                         "(Дата должна быть в формате: ДД.ММ.ГГГГ)\n\n"
                                         "*Начало гарантийного периода типа 'Стандарт' начинается с даты покупки из чека!* "
                                         "*Сохраните чек, он понадобиться в случае обращения в Сервисный центр.*",
                                    keyboard=cancel_action_keyboard)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_purchase_date)

    except (IncorrectSerialNumberException, NotFoundDeviceBySerialNumberException, DeviceIsRegisteredException) as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_serial_number)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(RegistrationAndActivateGuaranteeState.set_purchase_date)
async def set_serial_number_and_update_data_in_registration(message: Message, state: FSMContext):
    """
    Метод принимает дату покупки устройства от пользователя и сохраняет данные.

    :param message: Сообщение пользователя
    :param state: Состояние
    """

    try:
        purchase_date = str(message.text)
        await is_correct_format_date(purchase_date)
        await is_correct_period_date(purchase_date)

        purchase_date = datetime.strptime(purchase_date, "%d.%m.%Y").date()

        state_dict = await state.get_data()

        # Обновляем информацию по устройству
        device = await device_service.get_device_by_serial_number_and_user_id(serial_number= state_dict["set_serial_number"],
                                                                              user_id=message.from_user.id)
        device.purchase_date = purchase_date

        device = await device_service.update_device(device)

        # Обновляем информацию по пользователю
        user = await user_service.get_user(message.chat.id)
        user.name = state_dict["set_name"]
        user.surname = state_dict["set_surname"]
        user.phone = state_dict["set_phone"]
        user.email = state_dict["set_email"]
        user.city = state_dict.get("set_city")
        user.order_source = state_dict.get("set_order_source")

        user = await user_service.update_user(user)

        await state.clear()

        await send_check_user_and_device_data_message(message, user, device)

    except (IncorrectDateOfPurchaseException, IncorrectPeriodDateException) as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(RegistrationAndActivateGuaranteeState.set_purchase_date)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


###
###### Работа с выбором Гарантийного плана
####
##


@router.callback_query(UserDataApproveCall.filter())
async def choice_guarantee_type_call(call: CallbackQuery, callback_data: UserDataApproveCall):
    """
    Метод предлагает выбрать гарантийный план

    :param call: Вызов кнопки
    :param callback_data: Данные, переданные в кнопке
    """

    # Получаем информацию о стоимости гарантийного плана
    device_id = int(callback_data.device_id)

    await choice_guarantee_type_handler_service(event=call,device_id=device_id)


@router.callback_query(UpgradeStandardGuaranteeCall.filter())
async def upgrade_standard_guarantee_type(call: CallbackQuery, callback_data: UpgradeStandardGuaranteeCall):
    """
    Метод предлагает улучшить гарантийный план, если ранее был выбран тип "Стандарт"

    :param call: Вызов кнопки
    :param callback_data: Данные, переданные в кнопке
    """

    await delete_previous_message_and_send_new_from_call(call=call,
                                                         text='Вы выбрали тип "Стандарт". Не желаете выбрать более продвинутый план?',
                                                         keyboard=await get_upgrade_guarantee_type_keyboard( device_id=callback_data.device_id,
                                                                                                             guarantee_standard_price=callback_data.guarantee_standard_price,
                                                                                                             guarantee_comfort_price=callback_data.guarantee_comfort_price,
                                                                                                             guarantee_premium_price=callback_data.guarantee_premium_price))


@router.callback_query(GuaranteeTypeCall.filter())
async def set_guarantee_type(call: CallbackQuery, callback_data: GuaranteeTypeCall):
    """
    Метод принимает гарантийный план и сохраняет в БД

    :param call: Вызов кнопки
    :param callback_data: Данные, переданные в кнопке
    """

    guarantee_base = GuaranteeBase()
    device_id = callback_data.device_id
    device = await device_service.get_device_with_guarantee(device_id)
    user = await user_service.get_user(chat_id=call.message.chat.id)

    try:

        # Донасыщаем объект значениями из Inline клавиатуры
        await guarantee_base.enrich_from_inline_keyboard(device_id=device.id,
                                                         guarantee_type=callback_data.type,
                                                         guarantee_standard_price=callback_data.guarantee_standard_price)
                                                         # guarantee_comfort_price=callback_data.guarantee_comfort_price,
                                                         # guarantee_premium_price=callback_data.guarantee_premium_price)

        # Проверяем, что устройства еще не было ни одного гарантийного плана "Стандарт"
        if guarantee_base.guarantee_type == GuaranteeTypeEnum.STANDARD and not all(g.guarantee_type != GuaranteeTypeEnum.STANDARD for g in device.guarantees):
            raise DeviceHasStandardGuaranteeTypeException

        # Сохраняем гарантийный план в БД
        guarantee = await guarantee_service.create_guarantee_with_period(guarantee_base, device)

        guarantee_create_bitrix24_dto = GuaranteeCreateBitrix24RequestDTO(guarantee, device, user)
        guarantee_dto = GuaranteeResponseDTO(guarantee, device)

        # Создаем Сделку в Битрикс24
        await guarantee_service.create_guarantee_deal_in_bitrix24(guarantee_create_bitrix24_dto)

        # Генерируем и отправляем PDF сертификат (не блокируем логику при ошибке)
        pdf_path = None
        try:
            pdf_path = generate_certificate_pdf(user=user, device=device, guarantee=guarantee)
            await bot.send_document(
                call.message.chat.id,
                FSInputFile(pdf_path),
                caption="Цифровой гарантийный сертификат"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке PDF сертификата: {e}", extra={"service": "guarantee_handler"})
        finally:
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)

        await delete_previous_message_and_send_new_from_call(call=call,
                                                             text="Вы выбрали гарантийный план!\n\n" + await guarantee_dto.get_guarantee_text())
    except DeviceHasStandardGuaranteeTypeException as e:
        await send_exception_and_request_data_again_from_call(call=call,
                                                             exception_text=e)
        await choice_guarantee_type_handler_service(event=call,device_id=device_id)


###
###### Работы с редактированием введенных данных пользователя
####
##


@router.callback_query(UserDataUpdateCall.filter())
async def update_user_and_device_data(call: CallbackQuery, callback_data: UserDataUpdateCall):
    """
    Метод предоставляет выбор параметров для изменения

    :param call: Вызов кнопки
    :param callback_data: Данные, переданные в кнопке
    """

    await delete_previous_message_and_send_new_from_call(call=call,
                                                         text="Что хотите изменить?",
                                                         keyboard=await get_update_user_keyboard(device_id=callback_data.device_id))


@router.callback_query(UpdateUserCall.filter())
async def set_user_and_device_data(call: CallbackQuery, callback_data: UpdateUserCall,  state: FSMContext):
    """
    Метод запрашивает новые данные по выбранному параметру

    :param call: Вызов кнопки
    :param callback_data: Данные, переданные в кнопке
    :param state: Состояние
    """

    msg = ""
    new_state = None
    device_id = int(callback_data.device_id)
    param = str(callback_data.param)

    match param:
        case "name":
            new_state = UpdateUserAndDeviceDataState.name
            msg = "ваше _имя_"

        case "surname":
            new_state = UpdateUserAndDeviceDataState.surname
            msg = "вашу _фамилию_"

        case "phone":
            new_state = UpdateUserAndDeviceDataState.phone
            msg = ("ваш _номер телефона_ .\n"
                   "(Номер должен начинаться с +7, без пробелов и спец символов, и содержать 11 цифр)")

        case "email":
            new_state = UpdateUserAndDeviceDataState.email
            msg = ("ваш _Email_ .\n"
                   "(Email должен быть в формате: test@test.test)")

        case "serial_number":
            new_state = UpdateUserAndDeviceDataState.serial_number
            msg = ("_серийный номер_ вашего устройства.\n"
                   "(Серийный номер должен содержать набор цифр без пробелов)")

        case "purchase_date":
            new_state = UpdateUserAndDeviceDataState.purchase_date
            msg = ("_дату покупки_ вашего устройства, указанную в чеке.\n"
                   "(Дата должна быть в формате: ДД.ММ.ГГГГ)\n\n"
                   "*Начало гарантийного периода типа 'Стандарт' начинается с даты покупки из чека!* "
                   "*Сохраните чек, он понадобиться в случае обращения в Сервисный центр.*")

    await delete_previous_message_and_send_new_from_call(call=call,
                                                         text="Введите " + msg,
                                                         keyboard=cancel_action_keyboard)

    await state.set_state(new_state)
    await state.update_data(device_id = device_id)


@router.message(UpdateUserAndDeviceDataState.name)
async def set_name(message: Message, state: FSMContext):
    """
    Метод принимает на вход обновленное имя и сохраняет в БД

    :param message: Сообщение пользователя
    :param state: Состояние
    """
    try:
        state_dict = await state.get_data()
        device_id =  state_dict["device_id"]

        name = str(message.text)

        await is_correct_format_name(name)

        user = await user_service.set_name(chat_id=message.chat.id,
                                           name=name)
        device = await device_service.get_device(device_id)

        await send_check_user_and_device_data_message(message, user, device)

        await state.clear()

    except IncorrectNameException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserAndDeviceDataState.name)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserAndDeviceDataState.surname)
async def set_surname(message: Message, state: FSMContext):
    """
    Метод принимает на вход обновленную фамилию и сохраняет в БД

    :param message: Сообщение пользователя
    :param state: Состояние
    """
    try:
        state_dict = await state.get_data()
        device_id =  state_dict["device_id"]

        surname = str(message.text)

        await is_correct_format_name(surname)

        user = await user_service.set_surname(chat_id=message.chat.id,
                                              surname=surname)
        device = await device_service.get_device(device_id)

        await send_check_user_and_device_data_message(message, user, device)

        await state.clear()
    except IncorrectNameException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserAndDeviceDataState.surname)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserAndDeviceDataState.phone)
async def set_phone(message: Message, state: FSMContext):
    """
    Метод принимает на вход обновленный телефон и сохраняет в БД

    :param message: Сообщение пользователя
    :param state: Состояние
    """
    try:
        phone = str(message.text)
        state_dict = await state.get_data()
        device_id =  state_dict["device_id"]

        await is_correct_format_phone(phone)

        user = await user_service.set_phone(chat_id=message.chat.id,
                                            phone=phone)
        device = await device_service.get_device(device_id)

        await send_check_user_and_device_data_message(message, user, device)

        await state.clear()

    except IncorrectPhoneException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserAndDeviceDataState.phone)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserAndDeviceDataState.email)
async def set_email(message: Message, state: FSMContext):
    """
    Метод принимает на вход обновленный email пользователя, отправляет письмо с проверочным кодом и запрашивает его

    :param message: Сообщение пользователя
    :param state: Состояние
    """
    try:
        email = str(message.text)
        valid_email = await is_correct_format_email(email)
        await state.update_data(email=valid_email)

        checking_code = await send_checking_mail(valid_email)
        await state.update_data(checking_code=checking_code)

        await send_message_from_msg(message=message,
                                    text=f"На указанный электронный адрес {valid_email} было отправлено письмо с кодом подтверждения.\n"
                                         f"Если письмо не пришло, проверьте папку спам.\n\n"
                                         f"Пожалуйста введите код подтверждения из письма:",
                                    keyboard=await get_checking_email_keyboard(state="UpdateUserAndDeviceDataState"))

        await state.set_state(UpdateUserAndDeviceDataState.checking_code)

    except IncorrectEmailException as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserAndDeviceDataState.email)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserAndDeviceDataState.checking_code)
async def set_checking_number_and_update(message: Message, state: FSMContext):
    """
    Метод принимает проверочный код и сохранет обновленный email

    :param message: Сообщение от пользователя
    :param state: Состояние
    """
    try:
        checking_code_from_user = str(message.text)

        state_dict = await state.get_data()
        checking_code = state_dict["checking_code"]
        email = state_dict["email"]
        device_id = state_dict["device_id"]

        await is_correct_checking_email_code(code_from_user=checking_code_from_user,
                                             checking_code=checking_code)

        user = await user_service.set_email(chat_id=message.chat.id,
                                            email=email)

        device = await device_service.get_device(device_id)

        await send_check_user_and_device_data_message(message, user, device)

        await state.clear()

    except (IncorrectCheckingEmailCodeException, WrongCheckingEmailCodeException) as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserAndDeviceDataState.checking_code)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserAndDeviceDataState.serial_number)
async def set_serial_number(message: Message, state: FSMContext):
    """
    Метод принимает на вход обновленный серийный номер и сохраняет в БД

    :param message: Сообщение пользователя
    :param state: Состояние
    """

    try:

        serial_number = str(message.text)
        state_dict = await state.get_data()
        device_id =  state_dict["device_id"]

        await is_correct_format_serial_number(serial_number)

        device = await device_service.identify_device_and_update(device_id=device_id,
                                                                 serial_number=str(message.text))

        user = await user_service.get_user(chat_id=message.chat.id)

        await send_check_user_and_device_data_message(message, user, device)

        await state.clear()

    except (IncorrectSerialNumberException, NotFoundDeviceBySerialNumberException, DeviceIsRegisteredException) as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserAndDeviceDataState.serial_number)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.message(UpdateUserAndDeviceDataState.purchase_date)
async def set_purchase_date(message: Message, state: FSMContext):
    """
    Метод принимает на вход дату покупки устройства и сохраняет их в БД

    :param message: Сообщение пользователя
    :param state: Состояние
    """
    try:
        purchase_date = str(message.text)
        state_dict = await state.get_data()
        device_id = state_dict["device_id"]

        await is_correct_format_date(purchase_date)
        await is_correct_period_date(purchase_date)

        purchase_date = datetime.strptime(purchase_date, "%d.%m.%Y").date()

        device = await device_service.get_device(device_id=device_id)
        device.purchase_date = purchase_date

        new_device = await device_service.update_device(device)
        user = await user_service.get_user(chat_id=message.chat.id)

        await send_check_user_and_device_data_message(message, user, new_device)

        await state.clear()

    except (IncorrectDateOfPurchaseException, IncorrectPeriodDateException) as e:
        await send_exception_and_request_data_again_from_msg(message=message,
                                                             exception_text=e)
        await state.set_state(UpdateUserAndDeviceDataState.purchase_date)
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", extra={"service": "guarantee_handler"})
        await send_message_from_msg(message=message,
                                    text=f"Произошла непредвиденная ошибка, пожалуйста обратитесь к администратору!")


@router.callback_query(CheckingEmailCall.filter())
async def resend_checking_email(call: CallbackQuery, callback_data: CheckingEmailCall , state: FSMContext):
    """
    Метод перезапрашивает Email для отправки повторного письма с проверочным кодом

    :param callback_data: Данные, переданные в кнопке
    :param call: Текст кнопки
    :param state: Состояние
    """

    mapping_state = {
        "UpdateUserDataState": UpdateUserDataState.email,
        "RegistrationAndActivateGuaranteeState": RegistrationAndActivateGuaranteeState.set_email,
        "UpdateUserAndDeviceDataState": UpdateUserAndDeviceDataState.email
    }

    # Определяем следующее состояние из кнопки
    next_state = mapping_state[callback_data.state]

    await send_message_from_call(call=call,
                                 text="Введите ваш _Email_ .\n"
                                      "(Email должен быть в формате: test@test.test)",
                                 keyboard=cancel_action_keyboard)
    await state.set_state(next_state)