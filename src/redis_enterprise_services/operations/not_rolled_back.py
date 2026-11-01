from pydantic import BaseModel, Field


class NotRolledBack(BaseModel):
    cluster: str = Field(
        description="The cluster the resource is on.", examples=["https://cluster-a.net-a:9443"]
    )
    type: str = Field(
        description="database, acl, role, user, or permissions (the role-to-ACL links of the database).",
        examples=["acl"],
    )
    name: str = Field(
        description="The resource name. For permissions: the database name.", examples=["orders-app-acl"]
    )
    uid: int | None = Field(
        description="The resource uid on the cluster, or null when it is unknown whether it was created. "
        "For permissions: the database uid.",
        examples=[11],
    )
    error: str | None = Field(
        description="The last error of the resource: of its undo when the undo failed, "
        "otherwise of its step. Null when there was none.",
        examples=["cluster_unavailable: relay is down"],
    )
