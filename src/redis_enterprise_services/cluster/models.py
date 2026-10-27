from pydantic import BaseModel

from redis_enterprise_services.edge.models import ClusterCredentials


class ClusterAddress(BaseModel):
    network: str
    api_url: str


class ClusterTarget(ClusterAddress):
    credentials: ClusterCredentials
