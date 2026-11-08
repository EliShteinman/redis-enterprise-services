from pydantic import Field, PositiveFloat, SecretStr

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.network_name import NetworkName


class EdgeHeaderSettings(ConfigModel):
    method: str
    url: str
    authorization: str
    content_type: str
    error: str
    cluster_status: str
    cluster_state_id: str
    task_id: str
    result_ttl: str


class EdgeErrorCodeSettings(ConfigModel):
    invalid_request: str
    connection_failed: str
    response_rejected: str


class FirewallSettings(ConfigModel):
    header: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)


class NetworkSettings(ConfigModel):
    url: str = Field(pattern=r"^https?://")
    firewall: FirewallSettings | None


class EdgeSettings(ConfigModel):
    timeout_seconds: PositiveFloat
    headers: EdgeHeaderSettings
    content_type: str
    error_codes: EdgeErrorCodeSettings
    networks: dict[NetworkName, NetworkSettings]
