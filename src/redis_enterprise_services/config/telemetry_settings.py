from pydantic import BaseModel, Field, PositiveInt


class TelemetrySettings(BaseModel):
    service_name: str
    export_enabled: bool
    otlp_endpoint: str = Field(pattern=r"[^/]$")
    metrics_export_interval_ms: PositiveInt
    traces_path: str = Field(pattern=r"^/")
    metrics_path: str = Field(pattern=r"^/")
