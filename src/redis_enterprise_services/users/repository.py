import logging

from pydantic import JsonValue, TypeAdapter

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.cluster_settings import ClusterSettings
from redis_enterprise_services.config.user_settings import UserSettings
from redis_enterprise_services.users.models import CreatedUser, NewUser, User, UserCreationBody

USER_LIST_ADAPTER: TypeAdapter[list[User]] = TypeAdapter(type=list[User])

logger: logging.Logger = logging.getLogger(name=__name__)


class UserRepository:
    def __init__(self, *, api: ClusterApi, settings: UserSettings, cluster: ClusterSettings) -> None:
        self._api: ClusterApi = api
        self._settings: UserSettings = settings
        self._cluster: ClusterSettings = cluster

    def create(self, *, target: ClusterTarget, user: NewUser) -> CreatedUser:
        logger.info(msg=f"creating user {user.name} with roles {user.role_uids}")
        body: JsonValue = self._api.send(
            target=target, method="POST", path=self._settings.collection_path, body=creation_body(user=user)
        ).body
        return CreatedUser(user=User.model_validate(obj=body), action_uid=self._action_uid(body=body))

    def delete(self, *, target: ClusterTarget, uid: int) -> str | None:
        logger.info(msg=f"deleting user {uid}")
        body: JsonValue = self._api.send(
            target=target, method="DELETE", path=self._settings.path.format(uid=uid)
        ).body
        return self._action_uid(body=body)

    def find_by_name(self, *, target: ClusterTarget, name: str) -> User | None:
        body: JsonValue = self._api.send(
            target=target, method="GET", path=self._settings.collection_path
        ).body
        return next((user for user in USER_LIST_ADAPTER.validate_python(body) if user.name == name), None)

    def _action_uid(self, *, body: JsonValue) -> str | None:
        return string_field(body=body, name=self._cluster.fields.action_uid)


def creation_body(*, user: NewUser) -> dict[str, JsonValue]:
    return UserCreationBody(name=user.name, password=user.password, role_uids=user.role_uids).model_dump()
