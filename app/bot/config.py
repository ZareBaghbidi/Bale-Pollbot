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
    developers: Annotated[Set[int], NoDecode] = Field(default_factory=set, alias="DEVELOPERS")
    admin_class_access: Annotated[dict[int, Set[int] | str], NoDecode] = Field(
        default_factory=dict, alias="ADMIN_CLASS_ACCESS")

    model_config = SettingsConfigDict(
        env_file="app/.env",
        case_sensitive=False,
    )

    @field_validator("owners", "admins", "developers", mode="before")
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

    @field_validator("admin_class_access", mode="before")
    @classmethod
    def parse_admin_class_access(cls, v):
        if v is None or v == "":
            return {}
        if isinstance(v, str):
            v = json.loads(v)
        return {
            int(admin_id): ("*" if class_ids == "*" else
                            {int(class_id) for class_id in class_ids})
            for admin_id, class_ids in v.items()
        }


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


def save_admins(admin_ids: Set[int], admin_class_access=None) -> None:
    """Persist ADMIN IDs and their class access in app/.env."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    replacements = {
        "ADMINS": ",".join(str(uid) for uid in sorted(admin_ids)),
    }
    if admin_class_access is not None:
        serialized_access = {
            str(admin_id): ("*" if class_ids == "*" else
                            sorted(int(class_id) for class_id in class_ids))
            for admin_id, class_ids in admin_class_access.items()
        }
        replacements["ADMIN_CLASS_ACCESS"] = json.dumps(
            serialized_access, separators=(",", ":"), sort_keys=True)

    result = []
    found = set()
    for line in lines:
        key = line.partition("=")[0].strip()
        if key in replacements:
            if key not in found:
                result.append(f"{key}={replacements[key]}")
                found.add(key)
        else:
            result.append(line)
    for key, value in replacements.items():
        if key not in found:
            result.append(f"{key}={value}")
    env_path.write_text("\n".join(result) + "\n")
