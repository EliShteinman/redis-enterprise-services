from pydantic import BaseModel, Field


class ErrorInfo(BaseModel):
    code: str = Field(description="The error code from the contract.", examples=["step_rejected"])
    message: str = Field(
        description="What went wrong, for people; not for parsing.",
        examples=["cluster answered 406: Cannot allocate nodes for shards"],
    )
    cluster: str | None = Field(
        default=None,
        exclude_if=lambda cluster: cluster is None,
        description="The cluster the error came from. Only for errors from a cluster.",
        examples=["https://cluster-a.net-a:9443"],
    )
    cluster_error_code: str | None = Field(
        default=None,
        exclude_if=lambda code: code is None,
        description="The cluster's own error code. Only for errors from a cluster.",
        examples=["insufficient_resources"],
    )
