from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.planning.creation_step_keys import acl_step_key, role_step_key, user_step_key
from redis_enterprise_services.planning.database_spec import DatabaseUserSpec
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming


class UserResource(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    kind: Literal["acl", "role", "user"]
    name: str
    step_key: str


class UserResources(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    acl: UserResource
    role: UserResource
    user: UserResource

    def in_creation_order(self) -> list[UserResource]:
        return [self.acl, self.role, self.user]


def user_resources(
    *, naming: UserResourceNaming, database_name: str, user: DatabaseUserSpec
) -> UserResources:
    return UserResources(
        acl=UserResource(
            kind="acl",
            name=naming.acl_name(database_name=database_name, user_name=user.name),
            step_key=acl_step_key(user=user),
        ),
        role=UserResource(
            kind="role",
            name=naming.role_name(database_name=database_name, user_name=user.name),
            step_key=role_step_key(user=user),
        ),
        user=UserResource(kind="user", name=user.name, step_key=user_step_key(user=user)),
    )
