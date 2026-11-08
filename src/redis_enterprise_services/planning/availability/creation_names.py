from redis_enterprise_services.planning.availability.requested_name import RequestedName
from redis_enterprise_services.planning.database_creation_request import DatabaseCreationRequest
from redis_enterprise_services.planning.user_resource_names import UserResourceNames


class CreationNames:
    def __init__(self, *, resource_names: UserResourceNames) -> None:
        self._resource_names: UserResourceNames = resource_names

    def requested_names(self, *, request: DatabaseCreationRequest) -> list[RequestedName]:
        database: str = request.database.name
        per_user: list[RequestedName] = [
            requested
            for user in request.users
            for requested in (
                RequestedName(kind="acl", name=self._resource_names.acl(database=database, user=user.name)),
                RequestedName(kind="role", name=self._resource_names.role(database=database, user=user.name)),
                RequestedName(kind="user", name=user.name),
            )
        ]
        return [RequestedName(kind="database", name=database), *per_user]
