from string import Formatter
from typing import Annotated

from pydantic import AfterValidator, BaseModel

from redis_enterprise_services.config.role_management import RoleManagement

NAME_PLACEHOLDERS: set[str] = {"database", "user"}


def names_each_database_user(template: str) -> str:
    placeholders: set[str] = {field for _, field, _, _ in Formatter().parse(template) if field is not None}
    if placeholders != NAME_PLACEHOLDERS:
        raise ValueError(f"{template} must use exactly the placeholders {sorted(NAME_PLACEHOLDERS)}")
    return template


type NameTemplate = Annotated[str, AfterValidator(names_each_database_user)]


class DecompositionSettings(BaseModel):
    acl_name: NameTemplate
    role_name: NameTemplate
    role_management: RoleManagement
