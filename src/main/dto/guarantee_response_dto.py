from datetime import datetime, date

from main.model.device_base import DeviceBase
from main.model.guarantee_base import GuaranteeBase
from main.enum.guarantee_enum import GuaranteeInformationEnum, GuaranteeTypeEnum


class GuaranteeResponseDTO:

    def __init__(self, guarantee: GuaranteeBase, device: DeviceBase):
        self.id = guarantee.id,
        self.type = guarantee.guarantee_type
        self.price = guarantee.price
        self.start_date = guarantee.start_date
        self.end_date = guarantee.end_date
        self.remaining_length =  max((guarantee.end_date - date.today()).days, 0)
        self.device = device


    async def get_guarantee_text(self):
        """
        Метод возвращает текст с описанием гарантии

        :return: текст
        """
        type = None

        match self.type:
            case GuaranteeTypeEnum.STANDARD:
                type = GuaranteeInformationEnum.STANDARD
            case GuaranteeTypeEnum.COMFORT:
                type = GuaranteeInformationEnum.COMFORT
            case GuaranteeTypeEnum.PREMIUM:
                type = GuaranteeInformationEnum.PREMIUM

        text = (f"Информация о гарантийном плане\n"
                f"Тип: {type.value} {self.price}\n"
                f"Распространяется на модель *{self.device.model}* с серийным номером *{self.device.serial_number}*\n"
                f"Гарантия действует с *{self.start_date.strftime('%d.%m.%Y')}* по *{self.end_date.strftime('%d.%m.%Y')}\n*"
                f"Оставшийся гарантийный период: *{self.remaining_length} дней*")

        if self.type == GuaranteeTypeEnum.STANDARD:
            text = text + ("\n\n*Начало гарантийного периода типа 'Стандарт' начинается с даты покупки из чека!* "
                           "*Сохраните чек, он понадобиться в случае обращения в Сервисный центр.*")

        return text