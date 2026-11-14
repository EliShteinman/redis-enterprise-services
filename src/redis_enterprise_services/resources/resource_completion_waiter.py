from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import CreatedResource


class ResourceCompletionWaiter(Protocol):
    def wait_for_pending_creation(self, *, target: ClusterTarget, resource: CreatedResource) -> None: ...

    def wait_for_pending_deletion(
        self, *, target: ClusterTarget, uid: int, action_uid: str | None
    ) -> None: ...
