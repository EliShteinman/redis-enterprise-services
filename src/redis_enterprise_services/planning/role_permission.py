from pydantic import BaseModel


class RolePermission(BaseModel):
    role_uid: int
    redis_acl_uid: int
