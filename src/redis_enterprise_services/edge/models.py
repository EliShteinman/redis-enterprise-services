from pydantic import BaseModel, JsonValue

from redis_enterprise_services.connection.models import ClusterCredentials, HttpMethod


class ClusterRequest(BaseModel):
    method: HttpMethod
    url: str
    credentials: ClusterCredentials
    body: JsonValue | None = None
    cluster_state_id: int | None = None
    task_id: str | None = None
    result_ttl: int | None = None


class ClusterResponse(BaseModel):
    status_code: int
    headers: dict[str, str]
    body: JsonValue | None
    cluster_state_id: int | None
