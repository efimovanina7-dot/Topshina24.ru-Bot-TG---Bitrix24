import random
from email.mime.text import MIMEText
from aiosmtplib import SMTP

from main.config.log_config import logger
from main.config.mail_config import *


async def __send_mail(msg_object: MIMEText):
    """
    Метод отправляет электронное письмо

    :param msg_object: MIME-объект письма
    """

    try:
        smtp = SMTP(hostname=SMTP_SERVER, port=SMTP_PORT)
        # Устанавливаем соединение с сервером
        await smtp.connect()
        # Включаем шифрование STARTTLS
        await smtp.starttls()

        # Выполняем авторизацию
        await smtp.login(EMAIL_SENDER_ADDRESS, EMAIL_PASSWORD)

        # Отправляем сообщение
        await smtp.send_message(msg_object)

        # Закрываем соединение
        await smtp.quit()

        logger.debug("Письмо успешно отправлено", extra={"service": "mail"})

    except Exception as e:
        logger.error(f"Ошибка при отправке электронного письма: {e}", extra={"service": "mail"})
        raise Exception(e)


# ВРЕМЕННО ОТКЛЮЧЕНО: Верификация email
# Установите в True когда SMTP будет работать
EMAIL_VERIFICATION_ENABLED = False


async def send_checking_mail(email):
    """
    Метод отправляет жлектронное письмо для проверки mail адреса с проверочным кодом

    :param email: Электронный адрес
    :return: Проверочный код
    """

    # ВРЕМЕННО: Верификация отключена - возвращаем фиксированный код
    if not EMAIL_VERIFICATION_ENABLED:
        checking_code = 0000
        logger.info(f"[ВЕРИФИКАЦИЯ ОТКЛЮЧЕНА] Email {email} принят без проверки. Код: {checking_code}", extra={"service": "mail"})
        return checking_code

    try:
        # Генерация рандомного проверочного кода из 4 цифр
        checking_code = random.randint(1000, 9999)

        # Содержание письма
        subject = "ТОП ШИН 24. Проверка Email"
        body = ("Здравствуйте! Пожалуйста, подтвердите ваш email.\n"
                f"Ваш проверочный код: {checking_code}\n\n"
                f"С уважением, команда ТОП ШИН 24")

        # Создание MIME-объекта письма
        msg_object = MIMEText(body)
        msg_object["Subject"] = subject
        msg_object["From"] = EMAIL_SENDER_ADDRESS
        msg_object["To"] = email

        # Отправка письма
        await __send_mail(msg_object)

        logger.info(f"Письмо с проверочным кодом ({checking_code}) успешно отправлено на электронный адрес {email}", extra={"service": "mail"})

        return checking_code
    except Exception as e:
        logger.error(f"Ошибка при отправке электронного письма с проверочным кодом: {e}", extra={"service": "mail"})



