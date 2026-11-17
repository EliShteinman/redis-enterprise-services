from pydantic import PositiveFloat

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.validation.base_url import RelayUrl


class EdgeHeaderSettings(ConfigModel):
    cluster_method: str
    cluster_url: str
    cluster_authorization: str
    content_type: str
    edge_error_code: str
    cluster_status_code: str
    cluster_state_id: str
    returned_cluster_state_id: str
    crdb_task_id: str
    result_ttl_seconds: str
    network: str


class EdgeErrorCodeSettings(ConfigModel):
    invalid_request: str
    unauthorized: str
    connection_failed: str
    response_rejected: str


class EdgeSettings(ConfigModel):
    url: RelayUrl
    connect_timeout_seconds: PositiveFloat
    request_timeout_seconds: PositiveFloat
    headers: EdgeHeaderSettings
    request_content_type: str
    error_codes: EdgeErrorCodeSettings
