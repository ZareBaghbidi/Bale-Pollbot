from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from functools import lru_cache
from typing import Set


class AppSettings(BaseSettings):
    provider_token: str = Field(alias="PROVIDER_TOKEN")
    bale_bot_token: str = Field(alias="BALE_BOT_TOKEN")

    admins: Set[int] = Field(alias="ADMINS")

    model_config = SettingsConfigDict(
        env_file="app/.env",
        case_sensitive=False,
    )

    @field_validator("admins", mode="before")
    def parse_admins(cls, v):
        if isinstance(v, str):
            return {int(x.strip()) for x in v.split(",") if x.strip()}
        return v


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
