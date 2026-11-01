from pydantic import BaseModel


class OperationSettings(BaseModel):
    public_error_codes: dict[str, str]
