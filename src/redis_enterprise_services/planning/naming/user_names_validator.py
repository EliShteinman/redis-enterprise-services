from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming


class UserNamesValidator:
    def __init__(
        self,
        *,
        user_name_validator: NameValidator,
        acl_and_role_name_validator: NameValidator,
        resource_naming: UserResourceNaming,
    ) -> None:
        self._user_name_validator: NameValidator = user_name_validator
        self._acl_and_role_name_validator: NameValidator = acl_and_role_name_validator
        self._resource_naming: UserResourceNaming = resource_naming

    def ensure_valid(self, *, spec: DatabaseSpec, context: NamingContext) -> None:
        for user in spec.users:
            self._user_name_validator.ensure_valid(name=user.name, context=context)
            for derived_name in (
                self._resource_naming.acl_name(database_name=spec.database.name, user_name=user.name),
                self._resource_naming.role_name(database_name=spec.database.name, user_name=user.name),
            ):
                self._acl_and_role_name_validator.ensure_valid(name=derived_name, context=context)
