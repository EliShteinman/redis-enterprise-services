from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.resources.endpoint_repository import EndpointRepository


class AclRepository(EndpointRepository[NewAcl]):
    pass
