from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.propagators import TraceResponsePropagator, set_global_response_propagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from redis_enterprise_services.config.settings import TelemetrySettings

OTLP_TRACES_PATH: str = "/v1/traces"
OTLP_METRICS_PATH: str = "/v1/metrics"


class Telemetry:
    def __init__(self, *, settings: TelemetrySettings) -> None:
        resource: Resource = Resource.create(attributes={SERVICE_NAME: settings.service_name})
        self._tracer_provider: TracerProvider = self._build_tracer_provider(
            settings=settings, resource=resource
        )
        self._meter_provider: MeterProvider = self._build_meter_provider(settings=settings, resource=resource)

    @staticmethod
    def _build_tracer_provider(*, settings: TelemetrySettings, resource: Resource) -> TracerProvider:
        provider: TracerProvider = TracerProvider(resource=resource)
        if not settings.export_enabled:
            return provider
        exporter: OTLPSpanExporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint + OTLP_TRACES_PATH)
        provider.add_span_processor(span_processor=BatchSpanProcessor(span_exporter=exporter))
        return provider

    @staticmethod
    def _build_meter_provider(*, settings: TelemetrySettings, resource: Resource) -> MeterProvider:
        if not settings.export_enabled:
            return MeterProvider(resource=resource)
        exporter: OTLPMetricExporter = OTLPMetricExporter(endpoint=settings.otlp_endpoint + OTLP_METRICS_PATH)
        reader: MetricReader = PeriodicExportingMetricReader(
            exporter=exporter, export_interval_millis=settings.metrics_export_interval_ms
        )
        return MeterProvider(resource=resource, metric_readers=[reader])

    def start(self) -> None:
        trace.set_tracer_provider(tracer_provider=self._tracer_provider)
        metrics.set_meter_provider(meter_provider=self._meter_provider)
        LoggingInstrumentor().instrument(tracer_provider=self._tracer_provider, inject_trace_context=True)
        set_global_response_propagator(propagator=TraceResponsePropagator())
        HTTPXClientInstrumentor().instrument(
            tracer_provider=self._tracer_provider, meter_provider=self._meter_provider
        )

    def shutdown(self) -> None:
        self._tracer_provider.shutdown()
        self._meter_provider.shutdown()
