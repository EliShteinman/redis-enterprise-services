from redis_enterprise_services.planning.availability.requested_name import RequestedName
from redis_enterprise_services.planning.database_request import DatabaseRequest
from redis_enterprise_services.planning.resource_names import ResourceNames


class CreationNames:
    def __init__(self, *, names: ResourceNames) -> None:
        self._names: ResourceNames = names

    def of(self, *, request: DatabaseRequest) -> list[RequestedName]:
        database: str = request.database.name
        per_user: list[RequestedName] = [
            requested
            for user in request.users
            for requested in (
                RequestedName(kind="acl", name=self._names.acl(database=database, user=user.name)),
                RequestedName(kind="role", name=self._names.role(database=database, user=user.name)),
                RequestedName(kind="user", name=user.name),
            )
        ]
        return [RequestedName(kind="database", name=database), *per_user]
