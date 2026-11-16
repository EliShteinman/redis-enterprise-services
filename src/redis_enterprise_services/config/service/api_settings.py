import re

from pydantic import field_validator

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.validation.item_path import ApiPath


class ApiSettings(ConfigModel):
    liveness_path: ApiPath
    validation_error_message: str
    internal_error_message: str
    unexpected_error_message: str
    traceparent_pattern: re.Pattern[str]
    traceparent_error_message: str
    trace_id_pattern: re.Pattern[str]
    trace_id_error_message: str

    @field_validator("unexpected_error_message")
    @classmethod
    def reject_unknown_placeholders(cls, template: str) -> str:
        try:
            template.format(error_type=ValueError.__name__)
        except (KeyError, IndexError, ValueError, AttributeError, TypeError) as error:
            raise ValueError(
                f"unexpected_error_message cannot be filled with an error type alone: {error!r}"
            ) from error
        return template
