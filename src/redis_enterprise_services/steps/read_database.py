import logging
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsReader
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.cluster import IncompleteClusterObjectError
from redis_enterprise_services.resources.cluster_object_body import without_fields
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.steps.same_values import same_field

logger: logging.Logger = logging.getLogger(name=__name__)


class ReadDatabaseInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ClusterAddress
    uid: int
    expected_values: dict[str, JsonValue]


class ReadDatabaseStep(SagaStep[ReadDatabaseInput, DatabaseFieldsSnapshot]):
    def __init__(
        self,
        *,
        fields_reader: DatabaseFieldsReader,
        target_resolver: ClusterTargetResolver,
        settings: DatabaseSettings,
    ) -> None:
        self._fields_reader: DatabaseFieldsReader = fields_reader
        self._target_resolver: ClusterTargetResolver = target_resolver
        self._settings: DatabaseSettings = settings

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(
        self, *, step_input: ReadDatabaseInput, keep_result: KeepResult[DatabaseFieldsSnapshot]
    ) -> None:
        keep_result(result=self._complete_snapshot(step_input=step_input))

    def find_outcome(
        self,
        *,
        step_input: ReadDatabaseInput,
        kept_result: DatabaseFieldsSnapshot | None,
        keep_result_if_none_kept: KeepResult[DatabaseFieldsSnapshot],
    ) -> DatabaseFieldsSnapshot | None:
        if kept_result is not None:
            return kept_result
        snapshot: DatabaseFieldsSnapshot = self._complete_snapshot(step_input=step_input)
        keep_result_if_none_kept(result=snapshot)
        return snapshot

    def compensate(self, *, step_input: ReadDatabaseInput, result: DatabaseFieldsSnapshot) -> None:
        logger.info(msg=f"nothing to undo for the read of database {step_input.uid}")

    def _complete_snapshot(self, *, step_input: ReadDatabaseInput) -> DatabaseFieldsSnapshot:
        snapshot: DatabaseFieldsSnapshot = self._fields_reader.read(
            target=self._target_resolver.target_for(address=step_input.cluster), uid=step_input.uid
        )
        missing: list[str] = missing_database_values(values=snapshot.values, settings=self._settings)
        if missing:
            raise IncompleteClusterObjectError(
                message=f"database {step_input.uid} came back without a value for {missing}"
            )
        differing: list[str] = fields_not_holding(
            values=snapshot.values,
            expected=step_input.expected_values,
            order_insensitive_fields=self._settings.order_insensitive_fields,
        )
        if differing:
            raise IncompleteClusterObjectError(
                message=f"database {step_input.uid} does not hold what was set for {differing}"
            )
        return snapshot.model_copy(
            update={
                "values": without_fields(
                    fields=snapshot.values, names=frozenset(self._settings.secret_fields)
                )
            }
        )


def required_field_names(*, settings: DatabaseSettings) -> list[str]:
    return [*NewDatabase.model_fields, *settings.required_fields]


def missing_database_values(*, values: dict[str, JsonValue], settings: DatabaseSettings) -> list[str]:
    missing: list[str] = [
        name for name in required_field_names(settings=settings) if values.get(name) is None
    ]
    endpoints: JsonValue = values.get(settings.endpoints_field)
    if not isinstance(endpoints, list) or not endpoints:
        return [*missing, settings.endpoints_field]
    for index, endpoint in enumerate(endpoints):
        missing += [
            f"{settings.endpoints_field}[{index}].{name}"
            for name in settings.endpoint_fields
            if not isinstance(endpoint, dict) or is_empty(value=endpoint.get(name))
        ]
    return missing


def is_empty(*, value: JsonValue) -> bool:
    return value is None or value == "" or value == []


def fields_not_holding(
    *, values: dict[str, JsonValue], expected: dict[str, JsonValue], order_insensitive_fields: frozenset[str]
) -> list[str]:
    return [
        name
        for name, expected_value in expected.items()
        if name not in values
        or not same_field(
            current=values[name], expected=expected_value, ignore_order=name in order_insensitive_fields
        )
    ]
