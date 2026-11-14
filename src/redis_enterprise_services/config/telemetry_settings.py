from pydantic import Field, PositiveInt

from redis_enterprise_services.config.base_url import BaseUrl
from redis_enterprise_services.config.config_model import ConfigModel


class TelemetrySettings(ConfigModel):
    service_name: str
    export_enabled: bool
    otlp_endpoint: BaseUrl
    metrics_export_interval_ms: PositiveInt
    traces_path: str = Field(pattern=r"^/")
    metrics_path: str = Field(pattern=r"^/")
