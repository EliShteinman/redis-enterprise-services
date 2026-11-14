from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.cluster_access.http_method import HttpMethod


class ClusterRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: HttpMethod
    url: str
    credentials: ClusterCredentials
    body: JsonValue | None = None
    cluster_state_id: int | None = None
    crdb_task_id: str | None = None
    result_ttl_seconds: int | None = None


class ClusterResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status_code: int
    headers: dict[str, str]
    body: JsonValue | None
    cluster_state_id: int | None
