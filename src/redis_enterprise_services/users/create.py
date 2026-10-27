import logging

from redis_enterprise_services.cluster.actions import ActionWaiter
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.users.models import CreatedUser, NewUser, User
from redis_enterprise_services.users.repository import UserRepository

logger: logging.Logger = logging.getLogger(name=__name__)


class UserCreate:
    def __init__(
        self, *, repository: UserRepository, action_waiter: ActionWaiter, target: ClusterTarget, user: NewUser
    ) -> None:
        self._repository: UserRepository = repository
        self._action_waiter: ActionWaiter = action_waiter
        self._target: ClusterTarget = target
        self._user: NewUser = user
        self._created: User | None = None

    @property
    def created(self) -> User | None:
        return self._created

    def execute(self) -> None:
        creation: CreatedUser = self._repository.create(target=self._target, user=self._user)
        self._created = creation.user
        self._action_waiter.wait(target=self._target, action_uid=creation.action_uid)

    def compensate(self) -> None:
        if self._created is None:
            return
        logger.info(msg=f"removing created user {self._created.name}")
        action_uid: str | None = self._repository.delete(target=self._target, uid=self._created.uid)
        self._action_waiter.wait(target=self._target, action_uid=action_uid)
