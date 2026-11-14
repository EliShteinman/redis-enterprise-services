from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor  # pyright: ignore[reportMissingTypeStubs]
from opentelemetry.instrumentation.propagators import (
    TraceResponsePropagator,
    set_global_response_propagator,  # pyright: ignore[reportUnknownVariableType]
)
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from redis_enterprise_services.config.telemetry_settings import TelemetrySettings


class TelemetryProviders:
    def __init__(self, *, tracer_provider: TracerProvider, meter_provider: MeterProvider) -> None:
        self._tracer_provider: TracerProvider = tracer_provider
        self._meter_provider: MeterProvider = meter_provider

    def install(self) -> None:
        self._set_global_providers()
        self._instrument_libraries()

    def shutdown(self) -> None:
        self._tracer_provider.shutdown()
        self._meter_provider.shutdown()

    def _set_global_providers(self) -> None:
        trace.set_tracer_provider(tracer_provider=self._tracer_provider)
        metrics.set_meter_provider(meter_provider=self._meter_provider)

    def _instrument_libraries(self) -> None:
        LoggingInstrumentor().instrument(
            tracer_provider=self._tracer_provider,
            inject_trace_context=True,
            enable_log_auto_instrumentation=False,
        )
        set_global_response_propagator(propagator=TraceResponsePropagator())
        RequestsInstrumentor().instrument(
            tracer_provider=self._tracer_provider, meter_provider=self._meter_provider
        )


def build_telemetry_providers(*, settings: TelemetrySettings) -> TelemetryProviders:
    resource: Resource = Resource.create(attributes={SERVICE_NAME: settings.service_name})
    return TelemetryProviders(
        tracer_provider=build_tracer_provider(settings=settings, resource=resource),
        meter_provider=build_meter_provider(settings=settings, resource=resource),
    )


def build_tracer_provider(*, settings: TelemetrySettings, resource: Resource) -> TracerProvider:
    provider: TracerProvider = TracerProvider(resource=resource)
    if not settings.export_enabled:
        return provider
    exporter: OTLPSpanExporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint + settings.traces_path)
    provider.add_span_processor(span_processor=BatchSpanProcessor(span_exporter=exporter))
    return provider


def build_meter_provider(*, settings: TelemetrySettings, resource: Resource) -> MeterProvider:
    if not settings.export_enabled:
        return MeterProvider(resource=resource)
    exporter: OTLPMetricExporter = OTLPMetricExporter(endpoint=settings.otlp_endpoint + settings.metrics_path)
    reader: MetricReader = PeriodicExportingMetricReader(
        exporter=exporter, export_interval_millis=settings.metrics_export_interval_ms
    )
    return MeterProvider(resource=resource, metric_readers=[reader])
