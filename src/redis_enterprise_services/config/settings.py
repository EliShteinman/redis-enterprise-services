from typing import ClassVar, Self

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.config.background_settings import BackgroundSettings
from redis_enterprise_services.config.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.cluster_settings import ClusterSettings
from redis_enterprise_services.config.clusters_settings import ClusterList
from redis_enterprise_services.config.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.config.edge_network_coverage import networks_missing_from_edge
from redis_enterprise_services.config.edge_settings import EdgeSettings
from redis_enterprise_services.config.liveness_settings import LivenessSettings
from redis_enterprise_services.config.log_settings import LogSettings
from redis_enterprise_services.config.naming_settings import NamingSettings
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.config.role_settings import RoleSettings
from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.config.server_settings import ServerSettings
from redis_enterprise_services.config.state_settings import StateSettings
from redis_enterprise_services.config.telemetry_settings import TelemetrySettings
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings

YAML_FILES: tuple[str, ...] = (
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
    "config/user_resources.yaml",
    "config/naming.yaml",
    "config/operation.yaml",
    "config/background.yaml",
    "config/liveness.yaml",
)


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        yaml_file=YAML_FILES,
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RES_",
        env_nested_delimiter="__",
        extra="forbid",
    )

    log: LogSettings
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
    clusters: ClusterList
    database_defaults: DatabaseDefaultsSettings
    user_resources: UserResourcesSettings
    naming: NamingSettings
    operation: OperationSettings
    background: BackgroundSettings
    liveness: LivenessSettings
    cluster_credentials: ClusterCredentialsSettings

    @model_validator(mode="after")
    def every_cluster_network_has_an_edge(self) -> Self:
        missing: list[str] = networks_missing_from_edge(clusters=self.clusters, networks=self.edge.networks)
        if missing:
            raise ValueError(f"networks in clusters with no entry in edge.networks: {missing}")
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


def load_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
