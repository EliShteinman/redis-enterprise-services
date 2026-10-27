from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.edge.models import ClusterCredentials


class ClusterAddress(BaseModel):
    model_config = ConfigDict(revalidate_instances="always")

    network: str
    api_url: str


class ClusterTarget(ClusterAddress):
    credentials: ClusterCredentials
