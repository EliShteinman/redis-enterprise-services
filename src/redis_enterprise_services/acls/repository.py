from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.resources.endpoint_resource_repository import EndpointResourceRepository


class AclRepository(EndpointResourceRepository[NewAcl]):
    pass
