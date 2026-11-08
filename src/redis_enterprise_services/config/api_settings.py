import re

from redis_enterprise_services.config.config_model import ConfigModel


class ApiSettings(ConfigModel):
    validation_error_message: str
    internal_error_message: str
    traceparent_pattern: re.Pattern[str]
    traceparent_message: str
    trace_id_pattern: re.Pattern[str]
    trace_id_message: str
