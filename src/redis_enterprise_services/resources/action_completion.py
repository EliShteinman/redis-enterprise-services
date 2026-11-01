from redis_enterprise_services.cluster.action_tracker import ActionTracker
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.completion import CompletionWaiter
from redis_enterprise_services.resources.models import CreatedResource


class ActionCompletionWaiter(CompletionWaiter):
    def __init__(self, *, actions: ActionTracker) -> None:
        self._actions: ActionTracker = actions

    def wait_created(self, *, target: ClusterTarget, resource: CreatedResource) -> None:
        self._actions.wait(target=target, action_uid=resource.action_uid)

    def wait_deleted(self, *, target: ClusterTarget, uid: int, action_uid: str | None) -> None:
        self._actions.wait(target=target, action_uid=action_uid)
