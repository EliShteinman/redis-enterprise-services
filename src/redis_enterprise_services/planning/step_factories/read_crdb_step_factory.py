from functools import partial

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.keys.creation_step_keys import READ_CRDB_STEP_KEY
from redis_enterprise_services.planning.step_factories.crdb_step_factory import created_crdb_of
from redis_enterprise_services.resources.cluster_object_body import without_fields
from redis_enterprise_services.resources.creation_body_builder import CreationBodyBuilder
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.steps.crdb.read_crdb import CrdbConfigSnapshot, ReadCrdbInput


class ReadCrdbStepFactory:
    def __init__(
        self,
        *,
        read_crdb_step: SagaStep[ReadCrdbInput, CrdbConfigSnapshot],
        database_body_builder: CreationBodyBuilder[NewDatabase],
        secret_fields: frozenset[str],
    ) -> None:
        self._read_crdb_step: SagaStep[ReadCrdbInput, CrdbConfigSnapshot] = read_crdb_step
        self._database_body_builder: CreationBodyBuilder[NewDatabase] = database_body_builder
        self._secret_fields: frozenset[str] = secret_fields

    def step(
        self, *, coordinator: ClusterAddress, database: NewDatabase, settings: CrdbCreationSettings
    ) -> PreparableStep:
        return PlannedStep(
            key=READ_CRDB_STEP_KEY,
            step=self._read_crdb_step,
            build_input=partial(
                read_crdb_input,
                coordinator=coordinator,
                expected_config=without_fields(
                    fields=self._database_body_builder.creation_body(spec=database, cluster=coordinator),
                    names=self._secret_fields,
                ),
                expected_settings=settings,
            ),
        )


def read_crdb_input(
    *,
    step_results: StepResults,
    coordinator: ClusterAddress,
    expected_config: dict[str, JsonValue],
    expected_settings: CrdbCreationSettings,
) -> ReadCrdbInput:
    return ReadCrdbInput(
        coordinator=coordinator,
        guid=created_crdb_of(step_results=step_results).guid,
        expected_config=expected_config,
        expected_settings=expected_settings,
    )
