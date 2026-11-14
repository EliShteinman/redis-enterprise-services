from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class RolePermission(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    role_uid: int
    redis_acl_uid: int
