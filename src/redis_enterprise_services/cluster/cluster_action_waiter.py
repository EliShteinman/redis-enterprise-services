from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget


class ClusterActionWaiter(Protocol):
    def wait_until_completed(self, *, target: ClusterTarget, action_uid: str | None) -> None: ...
