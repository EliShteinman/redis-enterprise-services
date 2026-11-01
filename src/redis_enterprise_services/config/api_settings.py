import re

from pydantic import BaseModel


class ApiSettings(BaseModel):
    validation_error_message: str
    internal_error_message: str
    traceparent_pattern: re.Pattern[str]
    traceparent_message: str
