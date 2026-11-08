from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials


class ClusterTargetResolver(Protocol):
    def target_for(self, *, address: ClusterAddress) -> ClusterTarget: ...


class SharedCredentialsTargetResolver(ClusterTargetResolver):
    def __init__(self, *, credentials: ClusterCredentials) -> None:
        self._credentials: ClusterCredentials = credentials

    def target_for(self, *, address: ClusterAddress) -> ClusterTarget:
        return ClusterTarget(network=address.network, api_url=address.api_url, credentials=self._credentials)
