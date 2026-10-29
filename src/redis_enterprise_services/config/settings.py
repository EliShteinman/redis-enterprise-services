from typing import ClassVar

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.config.cluster_settings import ClusterSettings
from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.config.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.config.edge_settings import EdgeSettings
from redis_enterprise_services.config.log_settings import LoggingSettings
from redis_enterprise_services.config.resource_settings import ResourceSettings, RoleSettings
from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.config.server_settings import ServerSettings
from redis_enterprise_services.config.state_settings import StateSettings
from redis_enterprise_services.config.telemetry_settings import TelemetrySettings


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        yaml_file=(
            "config/log.yaml",
            "config/api.yaml",
            "config/telemetry.yaml",
            "config/edge.yaml",
            "config/action.yaml",
            "config/acl.yaml",
            "config/cluster.yaml",
            "config/database.yaml",
            "config/saga.yaml",
            "config/state.yaml",
            "config/role.yaml",
            "config/user.yaml",
            "config/server.yaml",
            "config/clusters.yaml",
            "config/database_defaults.yaml",
        ),
        env_prefix="RES_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    log: LoggingSettings
    api: ApiSettings
    telemetry: TelemetrySettings
    edge: EdgeSettings
    action: ActionSettings
    acl: ResourceSettings
    cluster: ClusterSettings
    database: DatabaseSettings
    saga: SagaSettings
    state: StateSettings
    role: RoleSettings
    user: ResourceSettings
    server: ServerSettings
    clusters: list[ClusterEntry]
    database_defaults: DatabaseDefaultsSettings

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


def load_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
