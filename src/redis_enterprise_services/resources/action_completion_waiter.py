from redis_enterprise_services.cluster.cluster_action_waiter import ClusterActionWaiter
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.resources.resource_completion_waiter import ResourceCompletionWaiter


class ActionCompletionWaiter(ResourceCompletionWaiter):
    def __init__(self, *, action_waiter: ClusterActionWaiter) -> None:
        self._action_waiter: ClusterActionWaiter = action_waiter

    def wait_for_pending_creation(self, *, target: ClusterTarget, resource: CreatedResource) -> None:
        self._action_waiter.wait_until_completed(target=target, action_uid=resource.action_uid)

    def wait_for_pending_deletion(self, *, target: ClusterTarget, uid: int, action_uid: str | None) -> None:
        self._action_waiter.wait_until_completed(target=target, action_uid=action_uid)
