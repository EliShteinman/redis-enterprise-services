from pydantic import BaseModel


class ApiSettings(BaseModel):
    validation_error_code: str
    validation_error_message: str
    internal_error_message: str
