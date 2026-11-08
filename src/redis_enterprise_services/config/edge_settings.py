from pydantic import BaseModel, PositiveFloat, SecretStr

from redis_enterprise_services.config.network_name import NetworkName


class EdgeHeaderSettings(BaseModel):
    method: str
    url: str
    authorization: str
    content_type: str
    error: str
    cluster_status: str
    cluster_state_id: str
    task_id: str
    result_ttl: str


class EdgeErrorCodeSettings(BaseModel):
    invalid_request: str
    connection_failed: str
    response_rejected: str


class FirewallSettings(BaseModel):
    header: str
    username: str
    password: SecretStr


class NetworkSettings(BaseModel):
    url: str
    firewall: FirewallSettings | None


class EdgeSettings(BaseModel):
    timeout_seconds: PositiveFloat
    headers: EdgeHeaderSettings
    content_type: str
    error_codes: EdgeErrorCodeSettings
    networks: dict[NetworkName, NetworkSettings]
