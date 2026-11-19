from typing import Protocol

from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse


class EdgeTransport(Protocol):
    def send(self, *, network: str, request: ClusterRequest) -> ClusterResponse: ...
