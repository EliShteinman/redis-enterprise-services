from redis_enterprise_services.resources.endpoint_resource_repository import EndpointResourceRepository
from redis_enterprise_services.users.models import NewUser


class UserRepository(EndpointResourceRepository[NewUser]):
    pass
