#!/usr/bin/env python3
"""
Тест создания контакта и сделки в Bitrix24 с выдуманными данными.
Проверяет, что поля клиента (ФИО, телефон, email, город, источник заказа)
попадают в пользовательские поля сделки UF_CRM_*.
"""
import sys
import asyncio
from pathlib import Path
from datetime import date

# Добавляем src в путь
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root / "src"))

from main.model.user_base import UserBase
from main.model.device_base import DeviceBase
from main.model.guarantee_base import GuaranteeBase
from main.enum.guarantee_enum import GuaranteeTypeEnum
from main.dto.guarantee_request_dto import GuaranteeCreateBitrix24RequestDTO
from main.service.integration.bitrix24_service import create_contact, create_guarantee_deal


def make_fake_user() -> UserBase:
    """Выдуманные данные клиента."""
    user = UserBase()
    user.chat_id = 123456789
    user.name = "Иван"
    user.surname = "Петров"
    user.phone = "+79990001123"
    user.email = "ivan.petrov.fake@example.com"
    user.city = "Переславль"
    user.order_source = "Ozon"
    user.pd_consent = True
    user.marketing_consent = False
    return user


def make_fake_device() -> DeviceBase:
    """Выдуманные данные устройства."""
    device = DeviceBase()
    device.model = "Шиномонтажный станок X-200"
    device.serial_number = "SN-TEST-2025-001"
    device.purchase_date = date(2025, 1, 15)
    return device


def make_fake_guarantee() -> GuaranteeBase:
    """Выдуманные данные гарантии."""
    guarantee = GuaranteeBase()
    guarantee.guarantee_type = GuaranteeTypeEnum.STANDARD
    guarantee.price = 990
    return guarantee


async def run_test():
    print("=== Тест Bitrix24: контакт + сделка (выдуманные данные) ===\n")

    user = make_fake_user()
    device = make_fake_device()
    guarantee = make_fake_guarantee()

    print("Данные клиента:", user.surname, user.name, user.phone, user.email, user.city, user.order_source)
    print("Устройство:", device.model, device.serial_number, device.purchase_date)
    print("Гарантия:", guarantee.guarantee_type.value, guarantee.price, "₽\n")

    # 1. Создать контакт в Bitrix24
    print("1. Создание контакта в Bitrix24...")
    try:
        contact_id = await create_contact(user)
        print(f"   Контакт создан, ID: {contact_id}\n")
    except Exception as e:
        print(f"   Ошибка создания контакта: {e}")
        return

    # 2. Создать сделку (гарантия) с привязкой к контакту
    dto = GuaranteeCreateBitrix24RequestDTO(guarantee, device, user)
    print("2. Создание сделки в воронке «Гарантия МП» с полями UF_CRM_*...")
    try:
        deal_id = await create_guarantee_deal(dto, contact_id)
        print(f"   Сделка создана, ID: {deal_id}\n")
    except Exception as e:
        print(f"   Ошибка создания сделки: {e}")
        return

    print("=== Тест завершён успешно ===")
    print("Проверьте в Bitrix24:")
    print("  - Контакт с именем «Иван Петров», город Переславль, телефон +79990001123")
    print("  - Сделку в воронке «Гарантия МП» с заполненными полями:")
    print("    Фамилия, Имя, Телефон, Email, Город (Переславль), Источник заказа (Ozon)")


if __name__ == "__main__":
    asyncio.run(run_test())
