from typing import ClassVar

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from redis_enterprise_services.config.edge_settings import EdgeSettings
from redis_enterprise_services.config.log_settings import LoggingSettings
from redis_enterprise_services.config.telemetry_settings import TelemetrySettings


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        yaml_file=("config/log.yaml", "config/telemetry.yaml", "config/edge.yaml"),
        env_prefix="RES_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    log: LoggingSettings
    telemetry: TelemetrySettings
    edge: EdgeSettings

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, env_settings, YamlConfigSettingsSource(settings_cls=settings_cls)
