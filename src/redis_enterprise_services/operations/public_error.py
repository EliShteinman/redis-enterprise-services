from pydantic import BaseModel, Field

from redis_enterprise_services.config.public_error_code import PublicErrorCode

PUBLIC_ERROR_CODE_DESCRIPTION: str = (
    "name_taken (a name is taken on the cluster), "
    "resources_locked (another operation holds the database or one of its users), "
    "invalid_name (a name breaks the naming rules), "
    "no_matching_cluster (no configured cluster for the target), "
    "cluster_request_failed (the cluster refused or failed a request), "
    "cluster_unavailable (the cluster or the edge service cannot be reached), "
    "cluster_timeout (the cluster did not finish in time), "
    "configuration_error (the service configuration cannot serve the request), "
    "internal_error (a bug in the service)."
)


class PublicError(BaseModel):
    code: PublicErrorCode = Field(
        description="What kind of failure: " + PUBLIC_ERROR_CODE_DESCRIPTION,
        examples=["cluster_request_failed"],
    )
    message: str = Field(
        description="What went wrong, for people; not for parsing.",
        examples=["cluster answered 406: Cannot allocate nodes for shards"],
    )
    cluster_url: str | None = Field(
        default=None,
        exclude_if=lambda cluster_url: cluster_url is None,
        description="The cluster the error came from. Only for errors from a cluster.",
        examples=["https://cluster-a.net-a:9443"],
    )
    cluster_error_code: str | None = Field(
        default=None,
        exclude_if=lambda cluster_error_code: cluster_error_code is None,
        description="The cluster's own error code. Only for errors from a cluster.",
        examples=["insufficient_resources"],
    )
