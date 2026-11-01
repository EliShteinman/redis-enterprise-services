from pydantic import BaseModel


class OperationError(BaseModel):
    code: str
    message: str
