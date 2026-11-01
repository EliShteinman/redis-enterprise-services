from redis_enterprise_services.resources.endpoint_repository import EndpointRepository
from redis_enterprise_services.users.models import NewUser


class UserRepository(EndpointRepository[NewUser]):
    pass
