from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterAnswer, ClusterTarget
from redis_enterprise_services.connection.models import HttpMethod


class ClusterCaller(Protocol):
    def send(
        self,
        *,
        target: ClusterTarget,
        method: HttpMethod,
        path: str,
        query: str | None = None,
        body: JsonValue | None = None,
        cluster_state_id: int | None = None,
    ) -> ClusterAnswer: ...
