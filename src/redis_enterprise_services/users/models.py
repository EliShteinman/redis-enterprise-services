from pydantic import Field

from redis_enterprise_services.resources.spec import NamedSpec


class NewUser(NamedSpec):
    password: str = Field(min_length=1)
    role_uids: list[int] = Field(min_length=1)
