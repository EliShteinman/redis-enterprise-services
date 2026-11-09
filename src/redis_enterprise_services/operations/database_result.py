from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from redis_enterprise_services.config.cluster_inventory import Environment


class DatabasePermissionResult(BaseModel):
    user_uid: int = Field(description="The user's uid on this cluster.", examples=[12])
    user_name: str = Field(description="The user name, as the cluster stored it.", examples=["app"])
    user_password: str = Field(
        description="The user's password: the one the cluster accepted when it created the user "
        "(the cluster never returns passwords).",
        examples=["S3cure-Passw0rd"],
    )
    acl_uid: int = Field(description="The uid of the user's ACL on this cluster.", examples=[9])
    acl_rule: str = Field(
        description="The user's ACL rule, as the cluster stored it: which commands and which key prefix.",
        examples=["+@all ~orders:*"],
    )


class DatabaseEndpointResult(BaseModel):
    dns_name: str = Field(
        min_length=1, description="The DNS name clients connect to.", examples=["redis-12000.cluster-a.net-a"]
    )
    port: int = Field(description="The port clients connect to.", examples=[12000])
    addr: list[str] = Field(min_length=1, description="The endpoint's IP addresses.", examples=[["10.0.0.5"]])


class DatabaseAccessResult(BaseModel):
    endpoints: list[DatabaseEndpointResult] = Field(
        min_length=1, description="How clients reach the database on this cluster, as the cluster reports it."
    )


class ClusterDatabaseResult(BaseModel):
    db_uid: int = Field(description="The database uid on this cluster.", examples=[7])
    settings: dict[str, JsonValue] = Field(
        description="Every field of the creation model (spec.database), as the database stored it on this "
        "cluster, read back after it became active.",
        examples=[
            {"name": "orders", "memory_size": 1073741824, "replication": True, "data_persistence": "aof"}
        ],
    )
    permissions: list[DatabasePermissionResult] = Field(
        description="One entry per user: the user and its ACL, which are created and deleted together."
    )


class DatabaseClusterResult(BaseModel):
    cluster: str = Field(description="The cluster name, as configured.", examples=["cluster-a"])
    cluster_url: str = Field(
        description="The API address of the cluster.",
        examples=["https://cluster-a.net-a:9443"],
    )
    network: str = Field(description="The network of the cluster.", examples=["net-a"])
    site: str = Field(description="The site of the cluster.", examples=["dc1"])
    environment: Environment = Field(description="The environment of the cluster.", examples=["PROD"])
    access: DatabaseAccessResult = Field(description="How clients connect to the database on this cluster.")
    db: ClusterDatabaseResult = Field(description="The database on this cluster, as the cluster stored it.")


class DatabaseResult(BaseModel):
    name: str = Field(description="The database name, as the cluster stored it.", examples=["orders"])
    memory_size: int = Field(
        description="The memory limit in bytes, as the cluster stored it.", examples=[1073741824]
    )
    active_active: bool = Field(
        description="Whether the database is Active-Active. Always false for now.", examples=[False]
    )
    crdb_guid: UUID | None = Field(
        description="The Active-Active database id. Null for a single-site database.", examples=[None]
    )
    clusters: list[DatabaseClusterResult] = Field(
        min_length=1, description="One entry per cluster that holds the database. One for now."
    )
