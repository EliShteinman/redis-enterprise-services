from pydantic import BaseModel


class TelemetrySettings(BaseModel):
    service_name: str
    export_enabled: bool
    otlp_endpoint: str
    metrics_export_interval_ms: int
