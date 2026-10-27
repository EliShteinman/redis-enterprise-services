import logging

from redis_enterprise_services.edge.models import ClusterTarget
from redis_enterprise_services.users.models import CreatedUser, NewUser, User
from redis_enterprise_services.users.repository import UserRepository

logger: logging.Logger = logging.getLogger(name=__name__)


class UserCreate:
    def __init__(self, *, repository: UserRepository, target: ClusterTarget, user: NewUser) -> None:
        self._repository: UserRepository = repository
        self._target: ClusterTarget = target
        self._user: NewUser = user
        self._created: User | None = None

    @property
    def created(self) -> User | None:
        return self._created

    def execute(self) -> None:
        creation: CreatedUser = self._repository.create(target=self._target, user=self._user)
        self._created = creation.user
        self._repository.wait_for_action(target=self._target, action_uid=creation.action_uid)

    def compensate(self) -> None:
        if self._created is None:
            return
        logger.info(msg=f"removing created user {self._created.name}")
        self._repository.delete(target=self._target, uid=self._created.uid)
