from redis_enterprise_services.cluster.actions import ActionWaiter
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import CreatedResource


class ActionCompletionWaiter:
    def __init__(self, *, action_waiter: ActionWaiter) -> None:
        self._action_waiter: ActionWaiter = action_waiter

    def wait_created(self, *, target: ClusterTarget, resource: CreatedResource) -> None:
        self._action_waiter.wait(target=target, action_uid=resource.action_uid)

    def wait_deleted(self, *, target: ClusterTarget, uid: int, action_uid: str | None) -> None:
        self._action_waiter.wait(target=target, action_uid=action_uid)
