from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.propagators import TraceResponsePropagator, set_global_response_propagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from redis_enterprise_services.config import TelemetrySettings

OTLP_TRACES_PATH: str = "/v1/traces"
OTLP_METRICS_PATH: str = "/v1/metrics"


class Telemetry:
    def __init__(self, *, settings: TelemetrySettings) -> None:
        resource: Resource = Resource.create(attributes={SERVICE_NAME: settings.service_name})
        self._tracer_provider: TracerProvider = TracerProvider(resource=resource)
        readers: list[MetricReader] = []
        if settings.export_enabled:
            self._tracer_provider.add_span_processor(
                span_processor=BatchSpanProcessor(
                    span_exporter=OTLPSpanExporter(endpoint=settings.otlp_endpoint + OTLP_TRACES_PATH)
                )
            )
            readers.append(
                PeriodicExportingMetricReader(
                    exporter=OTLPMetricExporter(endpoint=settings.otlp_endpoint + OTLP_METRICS_PATH),
                    export_interval_millis=settings.metrics_export_interval_ms,
                )
            )
        self._meter_provider: MeterProvider = MeterProvider(resource=resource, metric_readers=readers)

    def start(self) -> None:
        trace.set_tracer_provider(tracer_provider=self._tracer_provider)
        metrics.set_meter_provider(meter_provider=self._meter_provider)
        LoggingInstrumentor().instrument(tracer_provider=self._tracer_provider, inject_trace_context=True)
        set_global_response_propagator(propagator=TraceResponsePropagator())

    def shutdown(self) -> None:
        self._tracer_provider.shutdown()
        self._meter_provider.shutdown()
