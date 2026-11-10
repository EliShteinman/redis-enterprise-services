from typing import Annotated

from pydantic import AfterValidator

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.role_management import RoleManagement
from redis_enterprise_services.config.template_placeholders import reject_placeholders_other_than

NAME_PLACEHOLDERS: frozenset[str] = frozenset({"database", "user"})
NAME_SEPARATOR: str = "-"
JOINED_PLACEHOLDERS: str = f"{{database}}{NAME_SEPARATOR}{{user}}"


def reject_template_without_database_user_placeholders(template: str) -> str:
    reject_placeholders_other_than(template=template, allowed=NAME_PLACEHOLDERS)
    if JOINED_PLACEHOLDERS not in template:
        raise ValueError(f"{template} must join the placeholders as {JOINED_PLACEHOLDERS}")
    return template


type NameTemplate = Annotated[str, AfterValidator(reject_template_without_database_user_placeholders)]


class UserResourcesSettings(ConfigModel):
    acl_name_template: NameTemplate
    role_name_template: NameTemplate
    role_management: RoleManagement
