from pydantic import Field

from redis_enterprise_services.resources.spec import NamedSpec


class NewAcl(NamedSpec):
    acl: str = Field(min_length=1)
