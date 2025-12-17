from typing import Final

from main.config.dynaconf_config import config_setting

EMAIL_SENDER_ADDRESS: Final = config_setting.MAIL.ADDRESS
EMAIL_PASSWORD: Final = config_setting.MAIL.PASSWORD
SMTP_SERVER: Final = config_setting.MAIL.SMTP_SERVER
SMTP_PORT: Final = int(config_setting.MAIL.SMTP_PORT)