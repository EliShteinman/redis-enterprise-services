from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.endpoint import ResourceEndpoint
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.users.models import NewUser


class UserRepository:
    def __init__(self, *, endpoint: ResourceEndpoint) -> None:
        self._endpoint: ResourceEndpoint = endpoint

    def create(self, *, target: ClusterTarget, spec: NewUser) -> CreatedResource:
        return self._endpoint.create(target=target, body=spec.model_dump())

    def delete(self, *, target: ClusterTarget, uid: int) -> str | None:
        return self._endpoint.delete(target=target, uid=uid)

    def find_by_name(self, *, target: ClusterTarget, name: str) -> NamedResource | None:
        return self._endpoint.find_by_name(target=target, name=name)
