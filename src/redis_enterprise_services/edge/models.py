from pydantic import BaseModel, JsonValue

from redis_enterprise_services.cluster_access.models import ClusterCredentials, HttpMethod


class ClusterRequest(BaseModel):
    method: HttpMethod
    url: str
    credentials: ClusterCredentials
    body: JsonValue | None = None
    cluster_state_id: int | None = None
    crdb_task_id: str | None = None
    result_ttl_seconds: int | None = None


class ClusterResponse(BaseModel):
    status_code: int
    headers: dict[str, str]
    body: JsonValue | None
    cluster_state_id: int | None
