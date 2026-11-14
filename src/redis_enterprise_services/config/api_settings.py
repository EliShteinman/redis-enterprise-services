import re

from pydantic import field_validator

from redis_enterprise_services.config.config_model import ConfigModel


class ApiSettings(ConfigModel):
    validation_error_message: str
    internal_error_message: str
    unexpected_error_message: str
    traceparent_pattern: re.Pattern[str]
    traceparent_error_message: str

    @field_validator("unexpected_error_message")
    @classmethod
    def reject_unknown_placeholders(cls, template: str) -> str:
        sample: ValueError = ValueError("sample")
        try:
            template.format(error_type=type(sample).__name__, error=sample)
        except (KeyError, IndexError, ValueError, AttributeError, TypeError) as error:
            raise ValueError(
                f"unexpected_error_message cannot be filled with an error type and an error: {error!r}"
            ) from error
        return template
