from pydantic import BaseModel

from redis_enterprise_services.config.role_management import RoleManagement


class DecompositionSettings(BaseModel):
    acl_name: str
    role_name: str
    role_management: RoleManagement
