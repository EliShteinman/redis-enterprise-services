from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.models import HttpMethod


class ClusterApiCaller(Protocol):
    def send(
        self,
        *,
        target: ClusterTarget,
        method: HttpMethod,
        path: str,
        query: str | None = None,
        body: JsonValue | None = None,
        cluster_state_id: int | None = None,
    ) -> SuccessfulClusterResponse: ...
