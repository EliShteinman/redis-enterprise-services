from typing import ClassVar, Literal

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from redis_enterprise_services.config.edge_settings import EdgeSettings


class LoggingSettings(BaseModel):
    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    line_pattern: str
    date_format: str


class TelemetrySettings(BaseModel):
    service_name: str
    export_enabled: bool
    otlp_endpoint: str
    metrics_export_interval_ms: int


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        yaml_file="config/settings.yaml", env_prefix="RES_", env_nested_delimiter="__", extra="forbid"
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
