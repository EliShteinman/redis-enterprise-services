from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.user_resources import UserResources, user_resources


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
            resources: UserResources = user_resources(
                naming=self._resource_naming, database_name=spec.database.name, user=user
            )
            self._user_name_validator.ensure_valid(name=resources.user.name, context=context)
            for derived in (resources.acl, resources.role):
                self._acl_and_role_name_validator.ensure_valid(name=derived.name, context=context)
