from pydantic import BaseModel


class ApiSettings(BaseModel):
    validation_error_message: str
    internal_error_message: str
