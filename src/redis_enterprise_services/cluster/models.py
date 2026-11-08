from typing import ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.cluster_access.models import ClusterCredentials


class ClusterAddress(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(revalidate_instances="always", frozen=True)

    network: str
    api_url: str


class ClusterTarget(ClusterAddress):
    credentials: ClusterCredentials


class SuccessfulClusterResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    body: JsonValue | None
    cluster_state_id: int | None
