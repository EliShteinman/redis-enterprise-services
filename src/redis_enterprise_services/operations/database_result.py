from uuid import UUID

from pydantic import BaseModel, Field

from redis_enterprise_services.config.clusters_settings import Environment


class DatabaseUserResult(BaseModel):
    name: str
    user_uid: int
    role_uid: int
    acl_uid: int


class ClusterDatabase(BaseModel):
    url: str
    network: str
    site: str
    environment: Environment
    db_uid: int
    users: list[DatabaseUserResult] = Field(default_factory=list)


class DatabaseResult(BaseModel):
    name: str
    active_active: bool
    db_id: int | UUID
    clusters: list[ClusterDatabase]
