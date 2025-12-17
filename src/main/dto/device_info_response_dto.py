from datetime import date

from main.enum.device_type_enum import DeviceTypeEnum
from main.enum.guarantee_enum import GuaranteeTypeEnum
from main.model.device_base import DeviceBase
from main.model.guarantee_base import GuaranteeBase


class DeviceInfoResponseRTO():

    type: DeviceTypeEnum
    model: str
    serial_number: str
    purchase_date: date
    guarantees: []

    def __init__(self, device: DeviceBase):

        self.type = device.type
        self.model = device.model
        self.serial_number = device.serial_number
        self.purchase_date = device.purchase_date
        self.guarantees = device.guarantees
        self.latest_guarantee = max(device.guarantees, key=lambda g: g.start_date, default=None)


    async def get_device_info_text(self):
        """
        Метод возвращает текст с описанием устройства и последней гарантии

        :return: текст
        """
        remaining_length =  max((self.latest_guarantee.end_date - date.today()).days, 0)

        text = ("*Устройство*\n\n"
                f"🔸 Тип: _{self.type.value}_\n"
                f"🔸 Модель: _{self.model}_\n"
                f"🔸 Серийный номер: _{self.serial_number}_\n"
                f"🔸 Дата покупки: _{(self.purchase_date).strftime('%d.%m.%Y')}_"
                "\n\n*Последний гарантийный план*\n\n"
                f"🔸 Тип: _{self.latest_guarantee.guarantee_type.value}_\n"
                f"🔸 Гарантия действует с _{self.latest_guarantee.start_date.strftime('%d.%m.%Y')}_ по _{self.latest_guarantee.end_date.strftime('%d.%m.%Y')}_\n"
                f"🔸 Оставшийся гарантийный период: _{remaining_length}_ дней"
                )

        if self.latest_guarantee.guarantee_type == GuaranteeTypeEnum.STANDARD:
            text = text + ("\n\n*Начало гарантийного периода типа 'Стандарт' начинается с даты покупки из чека!* "
                           "*Сохраните чек, он понадобиться в случае обращения в Сервисный центр.*")

        return text