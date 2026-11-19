from typing import Literal

from pydantic import Field, JsonValue, SecretStr

from redis_enterprise_services.config.clusters.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.clusters.cluster_fqdn import ClusterFqdn
from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.validation.base_url import BaseUrl

type Environment = Literal["DEV", "PROD", "TEST"]
type ClusterType = Literal["generic", "dedicated"]

GENERIC_CLUSTER: ClusterType = "generic"


class ConfiguredCluster(ConfigModel):
    fqdn: ClusterFqdn
    environment: Environment
    network: str = Field(min_length=1)
    site: str = Field(min_length=1)
    type: ClusterType
    api_url: BaseUrl
    credentials: ClusterCredentialsSettings
    default_user_password: SecretStr = Field(min_length=1)
    database_override_levels: list[dict[str, JsonValue]] = Field(default_factory=list)
