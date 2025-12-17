from dynaconf import Dynaconf

# Парсинг файла с окружением
environment_setting = Dynaconf(
    settings_files=["resources/properties/env.yaml"],
    core_loaders=['YAML']
)

# Парсинг файла с настроечными конфигурациями в зависимости от текущего окружения
config_setting = getattr(
    Dynaconf(
        settings_files=["resources/properties/application_properties.yaml"],
        core_loaders=['YAML']
             ),
    environment_setting.ENVIRONMENT)

# Парсинг файла с id администраторов
security_setting = Dynaconf(
    settings_files = ["resources/properties/admin_id.yaml"],
    core_loaders=['YAML']
)