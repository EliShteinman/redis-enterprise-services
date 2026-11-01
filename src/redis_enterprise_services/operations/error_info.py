from pydantic import BaseModel, Field


class ErrorInfo(BaseModel):
    code: str
    message: str
    cluster: str | None = Field(default=None, exclude_if=lambda cluster: cluster is None)
    cluster_error_code: str | None = Field(default=None, exclude_if=lambda code: code is None)
