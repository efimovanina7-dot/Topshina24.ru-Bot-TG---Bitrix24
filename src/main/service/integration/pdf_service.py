from datetime import datetime
from pathlib import Path
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _safe(value):
    return value if value is not None else ""


# Регистрируем шрифт с кириллицей
FONT_NAME = "DejaVuSans"
FONT_PATH = Path(__file__).resolve().parents[3] / "resources" / "fonts" / "DejaVuSans.ttf"

# Регистрируем шрифт только если файл существует
if FONT_PATH.exists():
    try:
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))
        FONT_REGISTERED = True
    except Exception:
        # Если не удалось зарегистрировать, используем стандартный шрифт
        FONT_REGISTERED = False
        FONT_NAME = "Helvetica"
else:
    FONT_REGISTERED = False
    FONT_NAME = "Helvetica"


def generate_certificate_pdf(user, device, guarantee) -> Path:
    """
    Генерирует PDF сертификат и возвращает путь к файлу.
    Файл создаётся во временной директории /tmp/topshin_bot.
    """
    tmp_dir = Path("/tmp/topshin_bot")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    filename = f"certificate_{user.chat_id}_{device.serial_number or 'device'}.pdf"
    pdf_path = tmp_dir / filename

    c = canvas.Canvas(str(pdf_path), pagesize=A4)

    width, height = A4
    y = height - 50

    # Используем зарегистрированный шрифт или стандартный
    if FONT_REGISTERED:
        c.setFont(FONT_NAME, 18)
    else:
        c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "Цифровой гарантийный сертификат")
    y -= 30

    if FONT_REGISTERED:
        c.setFont(FONT_NAME, 12)
    else:
        c.setFont("Helvetica", 12)
    c.drawString(50, y, f"ФИО: {_safe(user.surname)} {_safe(user.name)}")
    y -= 18
    c.drawString(50, y, f"Телефон: {_safe(user.phone)}")
    y -= 18
    c.drawString(50, y, f"Email: {_safe(user.email)}")
    y -= 18

    c.drawString(50, y, f"Модель: {_safe(device.model)}")
    y -= 18
    c.drawString(50, y, f"Серийный номер: {_safe(device.serial_number)}")
    y -= 18
    c.drawString(50, y, f"Дата покупки: {_safe(device.purchase_date)}")
    y -= 18

    c.drawString(50, y, f"Тип гарантии: {_safe(guarantee.guarantee_type.value)}")
    y -= 18
    c.drawString(50, y, f"Срок действия: {_safe(guarantee.start_date)} — {_safe(guarantee.end_date)}")
    y -= 24

    c.drawString(50, y, "Сохраните этот сертификат — он подтверждает вашу гарантию.")
    y -= 18
    c.drawString(50, y, "Контакты поддержки: 89858546153")

    c.showPage()
    c.save()

    return pdf_path

