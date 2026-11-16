from pathlib import Path
from typing import ClassVar

import uvicorn
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from redis_enterprise_services.app import create_app
from redis_enterprise_services.config.settings import Settings, load_settings


class ConfigLocation(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(extra="ignore")

    config_dir: Path = Field(validation_alias="RES_CONFIG_DIR")


if __name__ == "__main__":
    location: ConfigLocation = ConfigLocation()  # pyright: ignore[reportCallIssue]
    settings: Settings = load_settings(config_dir=location.config_dir)
    uvicorn.run(
        app=create_app(settings=settings),
        host=settings.server.host,
        port=settings.server.port,
        log_config=None,
    )
