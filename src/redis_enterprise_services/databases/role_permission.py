from pydantic import BaseModel

ROLES_PERMISSIONS_FIELD: str = "roles_permissions"


class RolePermission(BaseModel):
    role_uid: int
    redis_acl_uid: int
