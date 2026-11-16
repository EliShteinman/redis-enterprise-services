from pathlib import Path
from typing import ClassVar, Self

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from redis_enterprise_services.config.clusters.cluster_flattening import configured_clusters
from redis_enterprise_services.config.clusters.cluster_tree import ClusterTree
from redis_enterprise_services.config.config_location import config_files
from redis_enterprise_services.config.crdb_settings import CrdbSettings
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.config.defaults.naming_settings import NamingSettings
from redis_enterprise_services.config.defaults.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.config.redis_api.action_settings import ActionSettings
from redis_enterprise_services.config.redis_api.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.redis_api.database_settings import DatabaseSettings
from redis_enterprise_services.config.redis_api.resource_settings import ResourceSettings
from redis_enterprise_services.config.redis_api.role_settings import RoleSettings
from redis_enterprise_services.config.service.api_settings import ApiSettings
from redis_enterprise_services.config.service.background_settings import BackgroundSettings
from redis_enterprise_services.config.service.edge_settings import EdgeSettings
from redis_enterprise_services.config.service.liveness_settings import LivenessSettings
from redis_enterprise_services.config.service.log_settings import LogSettings
from redis_enterprise_services.config.service.operation_settings import OperationSettings
from redis_enterprise_services.config.service.saga_settings import SagaSettings
from redis_enterprise_services.config.service.server_settings import ServerSettings
from redis_enterprise_services.config.service.state_settings import StateSettings
from redis_enterprise_services.config.service.telemetry_settings import TelemetrySettings


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RES_",
        env_nested_delimiter="__",
        extra="forbid",
        hide_input_in_errors=True,
    )

    log: LogSettings
    api: ApiSettings
    telemetry: TelemetrySettings
    edge: EdgeSettings
    action: ActionSettings
    crdb: CrdbSettings
    acl: ResourceSettings
    cluster_api: ClusterApiSettings
    database: DatabaseSettings
    saga: SagaSettings
    state: StateSettings
    role: RoleSettings
    user: ResourceSettings
    server: ServerSettings
    clusters: ClusterTree
    database_defaults: DatabaseDefaultsSettings
    user_resources: UserResourcesSettings
    naming: NamingSettings
    operation: OperationSettings
    background: BackgroundSettings
    liveness: LivenessSettings

    @model_validator(mode="after")
    def reject_clusters_that_cannot_be_configured(self) -> Self:
        configured_clusters(tree=self.clusters, api_scheme=self.cluster_api.scheme)
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls=settings_cls),
        )


def load_settings(*, config_dir: Path) -> Settings:
    class SettingsFromFiles(Settings):
        model_config: ClassVar[SettingsConfigDict] = Settings.model_config | SettingsConfigDict(
            yaml_file=config_files(config_dir=config_dir)
        )

    return SettingsFromFiles()  # pyright: ignore[reportCallIssue]
