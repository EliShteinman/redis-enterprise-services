from pydantic import BaseModel

from redis_enterprise_services.edge.models import ClusterCredentials


class ClusterTarget(BaseModel):
    network: str
    api_url: str
    credentials: ClusterCredentials
