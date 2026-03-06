"""
Конфигурация приложения
"""
import json
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""

    # Bot settings
    bot_token: str = Field(..., alias="BOT_TOKEN")
    bot_username: str = Field("", alias="BOT_USERNAME")

    # iiko settings
    IIKO_API_KEY: str = Field("", alias="IIKO_API_KEY")
    DEFAULT_ORG_ID: str = Field("73cbeaf9-b885-470f-b674-5bea708dd39f", alias="DEFAULT_ORG_ID")

    # Admin settings
    admin_user_ids: list[int] = Field(default_factory=list, alias="ADMIN_USER_IDS")

    # Database settings
    postgres_host: str = Field("localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field("botdb", alias="POSTGRES_DB")
    postgres_user: str = Field("botuser", alias="POSTGRES_USER")
    postgres_password: str = Field("", alias="POSTGRES_PASSWORD")

    # Redis settings
    redis_host: str = Field("localhost", alias="REDIS_HOST")
    redis_port: int = Field(6379, alias="REDIS_PORT")
    redis_db: int = Field(0, alias="REDIS_DB")
    redis_password: str = Field("", alias="REDIS_PASSWORD")

    # Environment
    env: str = Field("development", alias="ENV")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator('admin_user_ids', mode='before')
    def parse_admin_ids(cls, v):
        """Парсим список админов из JSON или строки с запятыми"""
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
        """Формирование URL для подключения к базе данных"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        """Формирование URL для подключения к Redis"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        return user_id in self.admin_user_ids


# Создаем глобальный экземпляр настроек
settings = Settings()
