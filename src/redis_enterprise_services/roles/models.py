from typing import Literal

from pydantic import Field

from redis_enterprise_services.resources.spec import NamedSpec

type RoleManagement = Literal["db_viewer", "db_member"]


class NewRole(NamedSpec):
    management: RoleManagement
    database_uids: list[int] = Field(min_length=1)
