from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget


class DatabaseActivationWaiter(Protocol):
    def wait_until_active(self, *, target: ClusterTarget, uid: int) -> None: ...
