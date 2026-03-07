"""
Конфигурация приложения
========================================
Загружает настройки из переменных окружения (файл .env) и предоставляет их
в виде атрибутов объекта settings. Используется библиотека pydantic-settings.
Все переменные имеют alice для соответствия именам в .env (верхний регистр).
"""

import json
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки бота, базы данных, Redis, iiko и администраторов."""

    # ---------- Bot settings ----------
    # Токен бота, полученный от @masterbot в MAX (обязательное поле)
    bot_token: str = Field(..., alias="BOT_TOKEN")

    # Имя пользователя бота (без @), используется для отображения
    bot_username: str = Field("", alias="BOT_USERNAME")

    # ---------- iiko settings ----------
    # Ключ API для доступа к iiko Cloud (обязателен для работы с iiko)
    IIKO_API_KEY: str = Field("", alias="IIKO_API_KEY")

    # Идентификатор организации по умолчанию в iiko
    DEFAULT_ORG_ID: str = Field("73cbeaf9-b885-470f-b674-5bea708dd39f", alias="DEFAULT_ORG_ID")

    # ---------- Admin settings ----------
    # Список числовых идентификаторов пользователей, имеющих права администратора.
    # Можно задать в .env как JSON-массив [123,456] или как строку через запятую "123,456".
    admin_user_ids: list[int] = Field(default_factory=list, alias="ADMIN_USER_IDS")

    # ---------- Database settings ----------
    # Хост сервера PostgreSQL (в Docker обычно 'postgres')
    postgres_host: str = Field("localhost", alias="POSTGRES_HOST")

    # Порт PostgreSQL
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")

    # Имя базы данных
    postgres_db: str = Field("botdb", alias="POSTGRES_DB")

    # Пользователь базы данных
    postgres_user: str = Field("botuser", alias="POSTGRES_USER")

    # Пароль пользователя базы данных
    postgres_password: str = Field("", alias="POSTGRES_PASSWORD")

    # ---------- Redis settings ----------
    # Хост Redis (в Docker обычно 'redis')
    redis_host: str = Field("localhost", alias="REDIS_HOST")

    # Порт Redis
    redis_port: int = Field(6379, alias="REDIS_PORT")

    # Номер базы данных Redis (по умолчанию 0)
    redis_db: int = Field(0, alias="REDIS_DB")

    # Пароль Redis (если требуется)
    redis_password: str = Field("", alias="REDIS_PASSWORD")

    # ---------- Environment and logging ----------
    # Окружение: development / production
    env: str = Field("development", alias="ENV")

    # Уровень логирования: DEBUG, INFO, WARNING, ERROR
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator('admin_user_ids', mode='before')
    def parse_admin_ids(cls, v):
        """Преобразует строку из .env в список целых чисел.

        Поддерживает JSON-массив "[123,456]" или строку через запятую "123,456".
        Возвращает список целых чисел.
        """
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [int(uid) for uid in parsed]
                else:
                    return [int(x.strip()) for x in v.split(',') if x.strip()]
            except (json.JSONDecodeError, ValueError):
                return [int(x.strip()) for x in v.split(',') if x.strip()]
        return v if isinstance(v, list) else []

    @property
    def database_url(self) -> str:
        """Полный URL для подключения к PostgreSQL (используется SQLAlchemy)."""
        return (f"postgresql://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}")

    @property
    def redis_url(self) -> str:
        """Полный URL для подключения к Redis."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def is_admin(self, user_id: int) -> bool:
        """Проверяет, является ли пользователь администратором."""
        return user_id in self.admin_user_ids


# Глобальный экземпляр настроек для использования во всём приложении
settings = Settings()
