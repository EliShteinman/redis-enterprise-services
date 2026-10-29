from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.connection.models import ClusterCredentials


class ClusterAddress(BaseModel):
    model_config = ConfigDict(revalidate_instances="always", frozen=True)

    network: str
    api_url: str


class ClusterTarget(ClusterAddress):
    credentials: ClusterCredentials


class ClusterAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)

    body: JsonValue | None
    cluster_state_id: int | None
