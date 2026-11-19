import logging
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.crdbs.models import Crdb
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.exceptions.cluster import IncompleteClusterObjectError
from redis_enterprise_services.resources.cluster_object_body import without_fields
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.steps.same_values import fields_not_holding

logger: logging.Logger = logging.getLogger(name=__name__)


class ReadCrdbInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    coordinator: ClusterAddress
    guid: str
    expected_config: dict[str, JsonValue]
    expected_settings: CrdbCreationSettings


class CrdbInstanceSettings(BaseModel):
    cluster_url: str
    id: int
    compression: int


class CrdbConfigSnapshot(BaseModel):
    default_db_config: dict[str, JsonValue]
    causal_consistency: bool
    encryption: bool
    featureset_version: int | None = None
    protocol_version: int | None = None
    instances: list[CrdbInstanceSettings] = Field(default_factory=list)


class ReadCrdbStep(SagaStep[ReadCrdbInput, CrdbConfigSnapshot]):
    def __init__(
        self,
        *,
        repository: CrdbRepository,
        target_resolver: ClusterTargetResolver,
        secret_fields: frozenset[str],
        order_insensitive_fields: frozenset[str],
        cluster_added_item_fields: frozenset[str],
    ) -> None:
        self._repository: CrdbRepository = repository
        self._target_resolver: ClusterTargetResolver = target_resolver
        self._secret_fields: frozenset[str] = secret_fields
        self._order_insensitive_fields: frozenset[str] = order_insensitive_fields
        self._cluster_added_item_fields: frozenset[str] = cluster_added_item_fields

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(self, *, step_input: ReadCrdbInput, keep_result: KeepResult[CrdbConfigSnapshot]) -> None:
        keep_result(result=self._checked_config(step_input=step_input))

    def find_outcome(
        self,
        *,
        step_input: ReadCrdbInput,
        kept_result: CrdbConfigSnapshot | None,
        keep_result_if_none_kept: KeepResult[CrdbConfigSnapshot],
    ) -> CrdbConfigSnapshot | None:
        if kept_result is not None:
            return kept_result
        snapshot: CrdbConfigSnapshot = self._checked_config(step_input=step_input)
        keep_result_if_none_kept(result=snapshot)
        return snapshot

    def compensate(self, *, step_input: ReadCrdbInput, result: CrdbConfigSnapshot) -> None:
        logger.info(msg=f"nothing to undo for the read of CRDB {step_input.guid}")

    def _checked_config(self, *, step_input: ReadCrdbInput) -> CrdbConfigSnapshot:
        crdb: Crdb = self._repository.read(
            target=self._target_resolver.target_for(address=step_input.coordinator), guid=step_input.guid
        )
        stored: dict[str, JsonValue] = without_fields(
            fields=crdb.default_db_config, names=self._secret_fields
        )
        raise_if_differing(
            guid=step_input.guid,
            differing=self._config_fields_not_holding(stored=stored, expected=step_input.expected_config)
            + sync_settings_not_holding(crdb=crdb, expected=step_input.expected_settings),
        )
        return snapshot_of(crdb=crdb, stored_config=stored, checked_settings=step_input.expected_settings)

    def _config_fields_not_holding(
        self, *, stored: dict[str, JsonValue], expected: dict[str, JsonValue]
    ) -> list[str]:
        return fields_not_holding(
            current=self._comparable(config=stored),
            expected=self._comparable(config=without_fields(fields=expected, names=self._secret_fields)),
            order_insensitive_fields=self._order_insensitive_fields,
        )

    def _comparable(self, *, config: dict[str, JsonValue]) -> dict[str, JsonValue]:
        return {
            name: without_item_fields(value=value, names=self._cluster_added_item_fields)
            for name, value in config.items()
        }


def without_item_fields(*, value: JsonValue, names: frozenset[str]) -> JsonValue:
    if not isinstance(value, list):
        return value
    return [
        {key: field for key, field in item.items() if key not in names} if isinstance(item, dict) else item
        for item in value
    ]


def raise_if_differing(*, guid: str, differing: list[str]) -> None:
    if differing:
        raise IncompleteClusterObjectError(message=f"CRDB {guid} does not hold what was sent for {differing}")


def snapshot_of(
    *, crdb: Crdb, stored_config: dict[str, JsonValue], checked_settings: CrdbCreationSettings
) -> CrdbConfigSnapshot:
    return CrdbConfigSnapshot(
        default_db_config=stored_config,
        causal_consistency=checked_settings.causal_consistency,
        encryption=checked_settings.encryption,
        featureset_version=crdb.featureset_version,
        protocol_version=crdb.protocol_version,
        instances=[
            CrdbInstanceSettings(
                cluster_url=instance.cluster.url, id=instance.id, compression=checked_settings.compression
            )
            for instance in crdb.instances
        ],
    )


def sync_settings_not_holding(*, crdb: Crdb, expected: CrdbCreationSettings) -> list[str]:
    held_and_expected: tuple[tuple[str, bool | None, bool], ...] = (
        ("causal_consistency", crdb.causal_consistency, expected.causal_consistency),
        ("encryption", crdb.encryption, expected.encryption),
    )
    differing: list[str] = [name for name, held, sent in held_and_expected if held != sent]
    return differing + [
        f"instances[{instance.id}].compression"
        for instance in crdb.instances
        if instance.compression != expected.compression
    ]
