import logging

from pydantic import JsonValue, TypeAdapter

from redis_enterprise_services.cluster.actions import ActionWaiter
from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.config.user_settings import UserSettings
from redis_enterprise_services.edge.models import ClusterTarget
from redis_enterprise_services.users.models import NewUser, User

ACTION_UID_FIELD: str = "action_uid"
USERS: TypeAdapter[list[User]] = TypeAdapter(type=list[User])

logger: logging.Logger = logging.getLogger(name=__name__)


class UserRepository:
    def __init__(self, *, api: ClusterApi, action_waiter: ActionWaiter, settings: UserSettings) -> None:
        self._api: ClusterApi = api
        self._action_waiter: ActionWaiter = action_waiter
        self._settings: UserSettings = settings

    def create(self, *, target: ClusterTarget, user: NewUser) -> User:
        logger.info(msg=f"creating user {user.name} with roles {user.role_uids}")
        body: JsonValue = self._api.send(
            target=target,
            method="POST",
            path=self._settings.collection_path,
            body={
                "name": user.name,
                "password": user.password.get_secret_value(),
                "role_uids": user.role_uids,
            },
        ).body
        self._wait_for_action(target=target, body=body)
        return User.model_validate(obj=body)

    def delete(self, *, target: ClusterTarget, uid: int) -> None:
        logger.info(msg=f"deleting user {uid}")
        body: JsonValue = self._api.send(
            target=target, method="DELETE", path=self._settings.path.format(uid=uid)
        ).body
        self._wait_for_action(target=target, body=body)

    def find_by_name(self, *, target: ClusterTarget, name: str) -> User | None:
        body: JsonValue = self._api.send(
            target=target, method="GET", path=self._settings.collection_path
        ).body
        return next((user for user in USERS.validate_python(body) if user.name == name), None)

    def _wait_for_action(self, *, target: ClusterTarget, body: JsonValue) -> None:
        action_uid: JsonValue = body.get(ACTION_UID_FIELD) if isinstance(body, dict) else None
        if isinstance(action_uid, str):
            self._action_waiter.wait(target=target, action_uid=action_uid)
