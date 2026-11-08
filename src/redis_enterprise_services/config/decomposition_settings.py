from string import Formatter
from typing import Annotated

from pydantic import AfterValidator

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.role_management import RoleManagement

NAME_PLACEHOLDERS: set[str] = {"database", "user"}
NAME_SEPARATOR: str = "-"
JOINED_PLACEHOLDERS: str = f"{{database}}{NAME_SEPARATOR}{{user}}"


def names_each_database_user(template: str) -> str:
    placeholders: set[str] = {field for _, field, _, _ in Formatter().parse(template) if field is not None}
    if placeholders != NAME_PLACEHOLDERS:
        raise ValueError(f"{template} must use exactly the placeholders {sorted(NAME_PLACEHOLDERS)}")
    if JOINED_PLACEHOLDERS not in template:
        raise ValueError(f"{template} must join the placeholders as {JOINED_PLACEHOLDERS}")
    return template


type NameTemplate = Annotated[str, AfterValidator(names_each_database_user)]


class DecompositionSettings(ConfigModel):
    acl_name: NameTemplate
    role_name: NameTemplate
    role_management: RoleManagement
