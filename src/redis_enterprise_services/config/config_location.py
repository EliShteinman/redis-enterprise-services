from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_FILE_NAMES: tuple[str, ...] = ("clusters.yaml", "defaults.yaml", "service.yaml", "redis_api.yaml")


class ConfigLocation(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    config_dir: Path = Field(validation_alias="RES_CONFIG_DIR")


def config_files(*, config_dir: Path) -> tuple[Path, ...]:
    return tuple(config_dir / name for name in CONFIG_FILE_NAMES)
