from redis_enterprise_services.planning.availability.requested_name import RequestedName
from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming


class CreationNames:
    def __init__(self, *, resource_naming: UserResourceNaming) -> None:
        self._resource_naming: UserResourceNaming = resource_naming

    def requested_names(self, *, spec: DatabaseSpec) -> list[RequestedName]:
        database_name: str = spec.database.name
        per_user: list[RequestedName] = [
            requested
            for user in spec.users
            for requested in (
                RequestedName(
                    kind="acl", name=self._resource_naming.acl_name(database=database_name, user=user.name)
                ),
                RequestedName(
                    kind="role", name=self._resource_naming.role_name(database=database_name, user=user.name)
                ),
                RequestedName(kind="user", name=user.name),
            )
        ]
        return [RequestedName(kind="database", name=database_name), *per_user]
