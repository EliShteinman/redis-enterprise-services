from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget


class ActionTracker(Protocol):
    def wait(self, *, target: ClusterTarget, action_uid: str | None) -> None: ...
