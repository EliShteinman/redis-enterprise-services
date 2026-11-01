from pydantic import BaseModel


class ErrorInfo(BaseModel):
    code: str
    message: str
