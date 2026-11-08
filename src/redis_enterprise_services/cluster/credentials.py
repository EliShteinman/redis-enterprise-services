from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.connection.models import ClusterCredentials


class ClusterCredentialsProvider(Protocol):
    def target_for(self, *, address: ClusterAddress) -> ClusterTarget: ...


class SharedCredentialsProvider(ClusterCredentialsProvider):
    def __init__(self, *, credentials: ClusterCredentials) -> None:
        self._credentials: ClusterCredentials = credentials

    def target_for(self, *, address: ClusterAddress) -> ClusterTarget:
        return ClusterTarget(network=address.network, api_url=address.api_url, credentials=self._credentials)
