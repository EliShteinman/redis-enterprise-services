from pydantic import Field

from redis_enterprise_services.config.role_management import RoleManagement
from redis_enterprise_services.resources.named_spec import NamedSpec


class NewRole(NamedSpec):
    management: RoleManagement
    database_uids: list[int] = Field(min_length=1)
