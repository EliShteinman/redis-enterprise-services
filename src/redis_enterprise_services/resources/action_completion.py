from redis_enterprise_services.cluster.cluster_action_waiter import ClusterActionWaiter
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.completion import CompletionWaiter
from redis_enterprise_services.resources.models import CreatedResource


class ActionCompletionWaiter(CompletionWaiter):
    def __init__(self, *, action_waiter: ClusterActionWaiter) -> None:
        self._action_waiter: ClusterActionWaiter = action_waiter

    def wait_created(self, *, target: ClusterTarget, resource: CreatedResource) -> None:
        self._action_waiter.wait_until_completed(target=target, action_uid=resource.action_uid)

    def wait_deleted(self, *, target: ClusterTarget, uid: int, action_uid: str | None) -> None:
        self._action_waiter.wait_until_completed(target=target, action_uid=action_uid)
