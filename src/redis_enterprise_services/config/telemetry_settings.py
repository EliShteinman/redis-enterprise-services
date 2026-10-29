from pydantic import BaseModel, PositiveInt


class TelemetrySettings(BaseModel):
    service_name: str
    export_enabled: bool
    otlp_endpoint: str
    metrics_export_interval_ms: PositiveInt
    traces_path: str
    metrics_path: str
