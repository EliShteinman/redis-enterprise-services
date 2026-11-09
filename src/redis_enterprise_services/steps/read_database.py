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
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind

logger: logging.Logger = logging.getLogger(name=__name__)


class ReadDatabaseInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ClusterAddress
    uid: int


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
        snapshot: DatabaseFieldsSnapshot = self._fields_reader.read_fields(
            target=self._target_resolver.target_for(address=step_input.cluster),
            uid=step_input.uid,
            field_names=read_field_names(settings=self._settings),
        )
        missing: list[str] = missing_database_values(values=snapshot.values, settings=self._settings)
        if missing:
            raise IncompleteClusterObjectError(
                message=f"database {step_input.uid} came back without a value for {missing}"
            )
        return snapshot


def read_field_names(*, settings: DatabaseSettings) -> list[str]:
    return [*NewDatabase.model_fields, *settings.read_fields]


def missing_database_values(*, values: dict[str, JsonValue], settings: DatabaseSettings) -> list[str]:
    missing: list[str] = [name for name in read_field_names(settings=settings) if values.get(name) is None]
    endpoints: JsonValue = values.get(settings.endpoints_field)
    if not isinstance(endpoints, list) or not endpoints:
        return sorted({*missing, settings.endpoints_field})
    for index, endpoint in enumerate(endpoints):
        missing += [
            f"{settings.endpoints_field}[{index}].{name}"
            for name in settings.endpoint_fields
            if not isinstance(endpoint, dict) or endpoint.get(name) is None
        ]
    return missing
