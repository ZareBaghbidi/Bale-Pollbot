from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic import Field, field_validator
from functools import lru_cache
from typing import Annotated, Set
from pathlib import Path
import json


class AppSettings(BaseSettings):
    provider_token: str = Field(alias="PROVIDER_TOKEN")
    bale_bot_token: str = Field(alias="BALE_BOT_TOKEN")

    owners: Annotated[Set[int], NoDecode] = Field(default_factory=set, alias="OWNERS")
    admins: Annotated[Set[int], NoDecode] = Field(default_factory=set, alias="ADMINS")

    model_config = SettingsConfigDict(
        env_file="app/.env",
        case_sensitive=False,
    )

    @field_validator("owners", "admins", mode="before")
    @classmethod
    def parse_id_list(cls, v):
        if v is None or v == "":
            return set()
        if isinstance(v, str):
            raw = v.strip()
            if not raw:
                return set()
            if raw.startswith("["):
                return {int(item) for item in json.loads(raw)}
            return {int(item.strip()) for item in raw.split(",") if item.strip()}
        return v


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


def save_admins(admin_ids: Set[int]) -> None:
    """Persist the limited ADMIN role list in app/.env."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    replacement = "ADMINS=" + ",".join(str(uid) for uid in sorted(admin_ids))
    result = []
    found = False
    for line in lines:
        if line.startswith("ADMINS="):
            if not found:
                result.append(replacement)
                found = True
        else:
            result.append(line)
    if not found:
        result.append(replacement)
    env_path.write_text("\n".join(result) + "\n")
