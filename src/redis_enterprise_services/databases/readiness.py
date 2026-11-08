from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget


class DatabaseReadiness(Protocol):
    def wait(self, *, target: ClusterTarget, uid: int) -> None: ...
