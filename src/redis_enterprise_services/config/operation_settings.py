from pydantic import BaseModel


class OperationSettings(BaseModel):
    public_error_codes: dict[str, str]
    cluster_error_codes: frozenset[str]
