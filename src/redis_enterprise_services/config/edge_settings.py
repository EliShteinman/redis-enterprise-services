from pydantic import Field, PositiveFloat, SecretStr

from redis_enterprise_services.config.config_model import ConfigModel


class EdgeHeaderSettings(ConfigModel):
    cluster_method: str
    cluster_url: str
    cluster_authorization: str
    content_type: str
    edge_error_code: str
    cluster_status_code: str
    cluster_state_id: str
    crdb_task_id: str
    result_ttl_seconds: str


class EdgeErrorCodeSettings(ConfigModel):
    invalid_request: str
    connection_failed: str
    response_rejected: str


class FirewallSettings(ConfigModel):
    authorization_header: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)


class EdgeNetworkSettings(ConfigModel):
    url: str = Field(pattern=r"^https?://.+")
    firewall: FirewallSettings | None


class EdgeSettings(ConfigModel):
    request_timeout_seconds: PositiveFloat
    headers: EdgeHeaderSettings
    request_content_type: str
    error_codes: EdgeErrorCodeSettings
    networks: dict[str, EdgeNetworkSettings]
