from uuid import UUID

from pydantic import BaseModel, Field

from redis_enterprise_services.config.clusters_settings import Environment


class DatabaseUserResult(BaseModel):
    name: str = Field(description="The user name.", examples=["app"])
    user_uid: int = Field(description="The user's uid on this cluster.", examples=[12])
    role_uid: int = Field(description="The uid of the user's role on this cluster.", examples=[4])
    acl_uid: int = Field(description="The uid of the user's ACL on this cluster.", examples=[9])


class ClusterDatabase(BaseModel):
    url: str = Field(
        description="The cluster address. Send it in target.clusters to edit or delete the database.",
        examples=["https://cluster-a.net-a:9443"],
    )
    network: str = Field(description="The network of the cluster.", examples=["net-a"])
    site: str = Field(description="The site of the cluster.", examples=["dc1"])
    environment: Environment = Field(description="The environment of the cluster.", examples=["PROD"])
    db_uid: int = Field(description="The database uid on this cluster.", examples=[7])
    users: list[DatabaseUserResult] = Field(default_factory=list, description="The users on this cluster.")


class DatabaseResult(BaseModel):
    name: str = Field(description="The database name.", examples=["orders"])
    active_active: bool = Field(description="Whether the database is Active-Active.", examples=[False])
    db_id: int | UUID = Field(
        description="The database id: its uid on a single site, the CRDB UUID in Active-Active. "
        "Send it in target.db_id to edit or delete the database.",
        examples=[7],
    )
    clusters: list[ClusterDatabase] = Field(description="One entry per site.")
