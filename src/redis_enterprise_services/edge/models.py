from typing import Literal

from pydantic import BaseModel, JsonValue, SecretStr

type HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class ClusterCredentials(BaseModel):
    username: str
    password: SecretStr


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


class ClusterTarget(BaseModel):
    network: str
    api_url: str
    credentials: ClusterCredentials
