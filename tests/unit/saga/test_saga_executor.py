from collections.abc import Callable

import pytest
from pydantic import BaseModel

from redis_enterprise_services.config.saga_settings import RetrySettings, SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.saga import InvalidPlanError, ResourcesLockedError
from redis_enterprise_services.saga.contract.failure import FailureCategory, FailureClassifier
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_lock import SagaLock
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordWriter
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.engine.compensator import Compensator
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor
from redis_enterprise_services.saga.engine.step_runner import StepRunner
from redis_enterprise_services.saga.plan.planned_step import BuildInput, PlannedStep
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.timing.sleeper import Sleeper

SAGA_ID: str = "trace-1"
LOCK_KEYS: list[str] = ["cluster1/db1"]
SETTINGS: SagaSettings = SagaSettings(
    step_retry=RetrySettings(attempts=3, backoff_step_seconds=1),
    compensation_retry=RetrySettings(attempts=2, backoff_step_seconds=1),
)


class RecordingSleeper(Sleeper):
    def __init__(self) -> None:
        self.slept: list[float] = []

    def sleep(self, *, seconds: float) -> None:
        self.slept.append(seconds)


class FakeError(RedisEnterpriseServicesError):
    def __init__(self, *, message: str, category: FailureCategory) -> None:
        super().__init__(message=message)
        self.category: FailureCategory = category


class FakeClassifier(FailureClassifier):
    def classify_step_error(self, *, error: RedisEnterpriseServicesError) -> FailureCategory:
        return error.category if isinstance(error, FakeError) else FailureCategory.FAILED

    def classify_find_outcome_error(self, *, error: RedisEnterpriseServicesError) -> FailureCategory:
        return self.classify_step_error(error=error)


BUSY: FakeError = FakeError(message="busy", category=FailureCategory.TRANSIENT)
FAILED: FakeError = FakeError(message="no", category=FailureCategory.FAILED)
OUTCOME_UNKNOWN: FakeError = FakeError(message="timeout", category=FailureCategory.OUTCOME_UNKNOWN)
AMBIGUOUS: FakeError = FakeError(message="two found", category=FailureCategory.REQUIRES_MANUAL_INTERVENTION)

type ScriptedExecution = str | RedisEnterpriseServicesError


class FakeInput(BaseModel):
    name: str
    parent: str | None = None


class FakeResult(BaseModel):
    name: str
    attempt: int


class FakeStep(SagaStep[FakeInput, FakeResult]):
    def __init__(
        self,
        *,
        calls: list[str],
        kind: StepKind = StepKind.COMPENSATABLE,
        execute_script: list[ScriptedExecution] | None = None,
        find_outcome_answers: list[FakeResult | RedisEnterpriseServicesError | None] | None = None,
        found_during_find_outcome: FakeResult | None = None,
        compensation_script: list[RedisEnterpriseServicesError | None] | None = None,
    ) -> None:
        self._calls: list[str] = calls
        self._kind: StepKind = kind
        self._execute_script: list[ScriptedExecution] = execute_script or ["keep"]
        self._find_outcome_answers: list[FakeResult | RedisEnterpriseServicesError | None] = (
            find_outcome_answers or []
        )
        self._found_during_find_outcome: FakeResult | None = found_during_find_outcome
        self._compensation_script: list[RedisEnterpriseServicesError | None] = compensation_script or [None]
        self.execute_calls: int = 0
        self.compensate_calls: int = 0

    @property
    def kind(self) -> StepKind:
        return self._kind

    def execute(self, *, step_input: FakeInput, keep_result: KeepResult[FakeResult]) -> None:
        action: ScriptedExecution = self._execute_script[
            min(self.execute_calls, len(self._execute_script) - 1)
        ]
        self.execute_calls += 1
        self._calls.append(f"execute {step_input.name}")
        if isinstance(action, RedisEnterpriseServicesError):
            raise action
        if action == "interrupt":
            raise SystemExit(1)
        keep_result(result=FakeResult(name=step_input.name, attempt=self.execute_calls))
        if action == "keep then interrupt":
            raise SystemExit(1)
        if action == "keep then busy":
            raise BUSY
        if action == "keep then failed":
            raise FAILED
        if action == "keep then outcome unknown":
            raise OUTCOME_UNKNOWN

    def find_outcome(
        self,
        *,
        step_input: FakeInput,
        kept_result: FakeResult | None,
        keep_result_if_none_kept: KeepResult[FakeResult],
    ) -> FakeResult | None:
        if self._found_during_find_outcome is not None:
            keep_result_if_none_kept(result=self._found_during_find_outcome)
        outcome: FakeResult | RedisEnterpriseServicesError | None = (
            self._find_outcome_answers.pop(0) if self._find_outcome_answers else None
        )
        if isinstance(outcome, RedisEnterpriseServicesError):
            raise outcome
        return outcome

    def compensate(self, *, step_input: FakeInput, result: FakeResult) -> None:
        self._calls.append(f"compensate {step_input.name}")
        error: RedisEnterpriseServicesError | None = self._compensation_script[
            min(self.compensate_calls, len(self._compensation_script) - 1)
        ]
        self.compensate_calls += 1
        if error is not None:
            raise error


class InMemorySagaRecordWriter(SagaRecordWriter):
    def __init__(self) -> None:
        self.saved: SagaRecord | None = None
        self.saved_final: bool = False

    def save(self, *, record: SagaRecord) -> None:
        self.saved = record.model_copy(deep=True)

    def save_final(self, *, record: SagaRecord) -> None:
        self.saved = record.model_copy(deep=True)
        self.saved_final = True


class InMemorySagaLock(SagaLock):
    def __init__(self, *, held_by: str | None = None) -> None:
        self.held_by: str | None = held_by

    def acquire(self, *, lock_keys: list[str], owner: str) -> None:
        if self.held_by is not None:
            raise ResourcesLockedError(message=f"{lock_keys} locked by {self.held_by}")
        self.held_by = owner

    def release(self, *, lock_keys: list[str], owner: str) -> None:
        if self.held_by == owner:
            self.held_by = None

    def raise_unless_held(self, *, lock_keys: list[str], owner: str) -> None:
        if self.held_by != owner:
            raise ResourcesLockedError(message=f"{lock_keys} locked by {self.held_by}")


def planned(
    *, step: FakeStep, key: str, build_input: BuildInput[FakeInput] | None = None
) -> PlannedStep[FakeInput, FakeResult]:
    return PlannedStep(
        key=key, step=step, build_input=build_input or (lambda step_results: FakeInput(name=key))
    )


@pytest.fixture
def calls() -> list[str]:
    return []


@pytest.fixture
def record_writer() -> InMemorySagaRecordWriter:
    return InMemorySagaRecordWriter()


@pytest.fixture
def lock() -> InMemorySagaLock:
    return InMemorySagaLock()


@pytest.fixture
def sleeper() -> RecordingSleeper:
    return RecordingSleeper()


def run(
    *,
    steps: list[PlannedStep[FakeInput, FakeResult]],
    record_writer: InMemorySagaRecordWriter,
    lock: InMemorySagaLock,
    sleeper: Sleeper | None = None,
    check_before_start: Callable[[], None] = lambda: None,
) -> SagaRecord:
    effective_sleeper: Sleeper = RecordingSleeper() if sleeper is None else sleeper
    executor: SagaExecutor = SagaExecutor(
        record_writer=record_writer,
        lock=lock,
        runner=StepRunner(settings=SETTINGS, classifier=FakeClassifier(), sleeper=effective_sleeper),
        compensator=Compensator(settings=SETTINGS, classifier=FakeClassifier(), sleeper=effective_sleeper),
    )
    return executor.run(
        saga_id=SAGA_ID,
        plan=SagaPlan(steps=list(steps), lock_keys=LOCK_KEYS),
        check_before_start=check_before_start,
    )


def statuses(record: SagaRecord) -> list[StepStatus]:
    return [step.status for step in record.steps]


def test_all_steps_done_succeeds_and_releases_the_lock(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    record: SagaRecord = run(
        steps=[planned(step=FakeStep(calls=calls), key=name) for name in ("a", "b")],
        record_writer=record_writer,
        lock=lock,
    )

    assert (record.status, statuses(record), lock.held_by) == (
        SagaStatus.SUCCEEDED,
        [StepStatus.DONE, StepStatus.DONE],
        None,
    )


def test_a_failed_step_compensates_the_earlier_steps_in_reverse(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(step=FakeStep(calls=calls), key="b"),
        planned(step=FakeStep(calls=calls, execute_script=[FAILED]), key="c"),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert (record.status, calls[-2:]) == (SagaStatus.ROLLED_BACK, ["compensate b", "compensate a"])


def test_a_transient_error_is_retried(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(calls=calls, execute_script=[BUSY, "keep"])

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, step.execute_calls) == (SagaStatus.SUCCEEDED, 2)


def test_an_unknown_outcome_that_is_found_is_done_without_running_again(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls, execute_script=[OUTCOME_UNKNOWN], find_outcome_answers=[FakeResult(name="a", attempt=0)]
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, step.execute_calls, record.steps[0].obtained_by) == (
        SagaStatus.SUCCEEDED,
        1,
        "found",
    )


def test_an_unknown_outcome_that_is_not_found_runs_the_step_again(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls, execute_script=[OUTCOME_UNKNOWN, "keep"], find_outcome_answers=[None]
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, step.execute_calls) == (SagaStatus.SUCCEEDED, 2)


def test_an_ambiguous_outcome_stops_for_manual_intervention_and_keeps_the_lock(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(
            step=FakeStep(calls=calls, execute_script=[OUTCOME_UNKNOWN], find_outcome_answers=[AMBIGUOUS]),
            key="b",
        ),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert (record.status, "compensate a" in calls, lock.held_by) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        False,
        SAGA_ID,
    )


def test_a_step_that_fails_for_manual_intervention_runs_once(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(calls=calls, execute_script=[AMBIGUOUS])

    run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert step.execute_calls == 1


def test_a_step_that_fails_for_manual_intervention_is_unresolved(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(step=FakeStep(calls=calls, execute_script=[AMBIGUOUS]), key="b"),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert statuses(record) == [StepStatus.DONE, StepStatus.UNRESOLVED]


def test_a_find_outcome_that_fails_for_a_known_reason_compensates_the_earlier_steps(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(
            step=FakeStep(calls=calls, execute_script=[OUTCOME_UNKNOWN], find_outcome_answers=[FAILED]),
            key="b",
        ),
    ]

    run(steps=steps, record_writer=record_writer, lock=lock)

    assert calls[-1] == "compensate a"


def test_a_result_found_before_a_failing_find_outcome_is_rolled_back(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls,
        execute_script=[OUTCOME_UNKNOWN],
        found_during_find_outcome=FakeResult(name="a", attempt=0),
        find_outcome_answers=[FAILED],
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, record.steps[0].obtained_by, calls[-1]) == (
        SagaStatus.ROLLED_BACK,
        "found",
        "compensate a",
    )


def test_a_failed_compensation_still_compensates_the_others_and_needs_manual_intervention(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(step=FakeStep(calls=calls, compensation_script=[FAILED]), key="b"),
        planned(step=FakeStep(calls=calls, execute_script=[FAILED]), key="c"),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert (record.status, statuses(record)[:2], lock.held_by) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        [StepStatus.COMPENSATED, StepStatus.COMPENSATION_FAILED],
        SAGA_ID,
    )


def test_a_failure_after_the_pivot_is_not_compensated(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(step=FakeStep(calls=calls, kind=StepKind.PIVOT), key="pivot"),
        planned(step=FakeStep(calls=calls, kind=StepKind.RETRIABLE, execute_script=[FAILED]), key="after"),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert (record.status, [entry for entry in calls if entry.startswith("compensate")]) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        [],
    )


def test_a_step_that_kept_a_result_and_stays_busy_is_compensated(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(calls=calls, execute_script=["keep then busy"])

    run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert calls[-1] == "compensate a"


def test_a_step_with_a_kept_result_finds_its_outcome_instead_of_running_again(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls, execute_script=["keep then busy"], find_outcome_answers=[FakeResult(name="a", attempt=1)]
    )

    run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert step.execute_calls == 1


def test_a_transient_error_after_a_kept_result_that_is_not_found_is_retried(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls, execute_script=["keep then busy", "keep"], find_outcome_answers=[None]
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, step.execute_calls) == (SagaStatus.SUCCEEDED, 2)


def test_a_step_run_again_after_its_kept_result_was_not_found_keeps_the_new_result(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls, execute_script=["keep then busy", "keep"], find_outcome_answers=[None]
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert record.steps[0].result == FakeResult(name="a", attempt=2).model_dump(mode="json")


def test_a_pivot_whose_kept_result_is_not_found_after_a_busy_cluster_is_not_run_again(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls,
        kind=StepKind.PIVOT,
        execute_script=["keep then busy", "keep"],
        find_outcome_answers=[None],
    )

    run(steps=[planned(step=step, key="p")], record_writer=record_writer, lock=lock)

    assert step.execute_calls == 1


@pytest.mark.parametrize(argnames="failing", argvalues=["keep then failed", "keep then outcome unknown"])
def test_a_non_transient_failure_after_a_kept_result_that_is_not_found_is_not_run_again(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock, failing: str
) -> None:
    step: FakeStep = FakeStep(calls=calls, execute_script=[failing, "keep"], find_outcome_answers=[None])

    run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert step.execute_calls == 1


def test_a_find_outcome_with_an_unknown_outcome_needs_manual_intervention_without_a_second_find(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls,
        execute_script=[OUTCOME_UNKNOWN],
        find_outcome_answers=[OUTCOME_UNKNOWN, FakeResult(name="a", attempt=0)],
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, lock.held_by) == (SagaStatus.REQUIRES_MANUAL_INTERVENTION, SAGA_ID)


def test_an_interrupted_saga_keeps_the_lock_and_leaves_its_running_step_unresolved(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    interrupted: FakeStep = FakeStep(calls=calls, execute_script=["interrupt"])

    with pytest.raises(expected_exception=SystemExit):
        run(
            steps=[planned(step=interrupted, key="a")],
            record_writer=record_writer,
            lock=lock,
        )

    assert (lock.held_by, record_writer.saved is not None and record_writer.saved.steps[0].status) == (
        SAGA_ID,
        StepStatus.UNRESOLVED,
    )


def test_a_later_step_builds_its_input_from_an_earlier_result(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    def child_input(step_results: StepResults) -> FakeInput:
        return FakeInput(name="b", parent=step_results.result_of(key="a", result_type=FakeResult).name)

    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(step=FakeStep(calls=calls), key="b", build_input=child_input),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert record.steps[1].step_input == {"name": "b", "parent": "a"}


def test_a_locked_database_runs_no_step(calls: list[str], record_writer: InMemorySagaRecordWriter) -> None:
    with pytest.raises(expected_exception=ResourcesLockedError):
        run(
            steps=[planned(step=FakeStep(calls=calls), key="a")],
            record_writer=record_writer,
            lock=InMemorySagaLock(held_by="other"),
        )

    assert calls == []


def test_an_unexpected_error_while_building_an_input_names_that_step(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    def broken_input(step_results: StepResults) -> FakeInput:
        raise ValueError("bug")

    with pytest.raises(expected_exception=ValueError):
        run(
            steps=[planned(step=FakeStep(calls=calls), key="a", build_input=broken_input)],
            record_writer=record_writer,
            lock=lock,
        )

    assert record_writer.saved is not None and record_writer.saved.stopped_at == "a"


def test_an_unexpected_error_needs_manual_intervention_and_keeps_the_lock(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    def broken_input(step_results: StepResults) -> FakeInput:
        raise ValueError("bug")

    with pytest.raises(expected_exception=ValueError):
        run(
            steps=[planned(step=FakeStep(calls=calls), key="a", build_input=broken_input)],
            record_writer=record_writer,
            lock=lock,
        )

    assert (record_writer.saved is not None and record_writer.saved.status, lock.held_by) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        SAGA_ID,
    )


def test_a_plan_with_two_pivots_is_refused(calls: list[str]) -> None:
    with pytest.raises(expected_exception=InvalidPlanError):
        SagaPlan(
            steps=[
                planned(step=FakeStep(calls=calls, kind=StepKind.PIVOT), key="first"),
                planned(step=FakeStep(calls=calls, kind=StepKind.PIVOT), key="second"),
            ],
            lock_keys=LOCK_KEYS,
        )


def test_a_compensatable_step_after_the_pivot_is_refused(calls: list[str]) -> None:
    with pytest.raises(expected_exception=InvalidPlanError):
        SagaPlan(
            steps=[
                planned(step=FakeStep(calls=calls, kind=StepKind.PIVOT), key="pivot"),
                planned(step=FakeStep(calls=calls), key="a"),
            ],
            lock_keys=LOCK_KEYS,
        )


def test_a_failure_after_a_retriable_step_without_a_pivot_is_not_compensated(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(step=FakeStep(calls=calls, kind=StepKind.RETRIABLE), key="b"),
        planned(step=FakeStep(calls=calls, kind=StepKind.RETRIABLE, execute_script=[FAILED]), key="c"),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert (record.status, calls[-1]) == (SagaStatus.REQUIRES_MANUAL_INTERVENTION, "execute c")


def test_a_first_retriable_step_that_fails_compensates_the_steps_before_it(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(step=FakeStep(calls=calls, kind=StepKind.RETRIABLE, execute_script=[FAILED]), key="b"),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert statuses(record)[0] is StepStatus.COMPENSATED


def test_repeated_step_keys_are_refused(calls: list[str]) -> None:
    with pytest.raises(expected_exception=InvalidPlanError):
        SagaPlan(
            steps=[
                planned(step=FakeStep(calls=calls), key="a"),
                planned(step=FakeStep(calls=calls), key="a"),
            ],
            lock_keys=LOCK_KEYS,
        )


def test_a_missing_earlier_result_fails_the_step_and_compensates_the_earlier_steps(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    def needs_missing(step_results: StepResults) -> FakeInput:
        return FakeInput(name="b", parent=step_results.result_of(key="missing", result_type=FakeResult).name)

    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(step=FakeStep(calls=calls), key="b", build_input=needs_missing),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert (record.status, calls[-1]) == (SagaStatus.ROLLED_BACK, "compensate a")


def test_an_ambiguous_find_outcome_marks_the_step_unresolved(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(calls=calls, execute_script=[OUTCOME_UNKNOWN], find_outcome_answers=[AMBIGUOUS])

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert record.steps[0].status is StepStatus.UNRESOLVED


class FinalSaveFailingRecordWriter(InMemorySagaRecordWriter):
    def save_final(self, *, record: SagaRecord) -> None:
        raise ConnectionError("state store is down")


def test_a_saga_whose_last_save_fails_keeps_the_lock(calls: list[str], lock: InMemorySagaLock) -> None:
    with pytest.raises(expected_exception=ConnectionError):
        run(
            steps=[planned(step=FakeStep(calls=calls), key="a")],
            record_writer=FinalSaveFailingRecordWriter(),
            lock=lock,
        )

    assert lock.held_by == SAGA_ID


@pytest.mark.parametrize(argnames="failure", argvalues=[FAILED, BUSY, OUTCOME_UNKNOWN])
def test_any_failure_after_an_unknown_outcome_needs_manual_intervention(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock, failure: FakeError
) -> None:
    step: FakeStep = FakeStep(
        calls=calls, execute_script=[OUTCOME_UNKNOWN, failure, "keep"], find_outcome_answers=[None]
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, lock.held_by) == (SagaStatus.REQUIRES_MANUAL_INTERVENTION, SAGA_ID)


def test_a_plan_without_a_lock_is_refused(calls: list[str]) -> None:
    with pytest.raises(expected_exception=InvalidPlanError):
        SagaPlan(steps=[planned(step=FakeStep(calls=calls), key="a")], lock_keys=[])


def test_a_plan_without_steps_is_refused() -> None:
    with pytest.raises(expected_exception=InvalidPlanError):
        SagaPlan(steps=[], lock_keys=LOCK_KEYS)


def test_a_compensation_that_fails_for_a_known_reason_is_not_retried(
    calls: list[str],
    record_writer: InMemorySagaRecordWriter,
    lock: InMemorySagaLock,
    sleeper: RecordingSleeper,
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls, compensation_script=[FAILED]), key="a"),
        planned(step=FakeStep(calls=calls, execute_script=[FAILED]), key="b"),
    ]

    run(steps=steps, record_writer=record_writer, lock=lock, sleeper=sleeper)

    assert calls.count("compensate a") == 1


def test_a_compensation_that_stays_busy_fails_after_its_attempts(
    calls: list[str],
    record_writer: InMemorySagaRecordWriter,
    lock: InMemorySagaLock,
    sleeper: RecordingSleeper,
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls, compensation_script=[BUSY]), key="a"),
        planned(step=FakeStep(calls=calls, execute_script=[FAILED]), key="b"),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock, sleeper=sleeper)

    assert (statuses(record)[0], calls.count("compensate a")) == (StepStatus.COMPENSATION_FAILED, 2)


@pytest.mark.parametrize(argnames="failure", argvalues=[BUSY, OUTCOME_UNKNOWN])
def test_a_compensation_that_fails_for_a_transient_or_unknown_reason_is_retried(
    calls: list[str],
    record_writer: InMemorySagaRecordWriter,
    lock: InMemorySagaLock,
    sleeper: RecordingSleeper,
    failure: FakeError,
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls, compensation_script=[failure, None]), key="a"),
        planned(step=FakeStep(calls=calls, execute_script=[FAILED]), key="b"),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock, sleeper=sleeper)

    assert (record.status, calls.count("compensate a")) == (SagaStatus.ROLLED_BACK, 2)


def test_a_failure_after_a_kept_result_lets_the_step_find_its_outcome(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls,
        execute_script=["keep then failed"],
        find_outcome_answers=[FakeResult(name="a", attempt=1)],
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, step.execute_calls) == (SagaStatus.SUCCEEDED, 1)


def test_only_the_first_kept_result_of_a_step_is_recorded(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls,
        execute_script=["keep then failed"],
        find_outcome_answers=[FakeResult(name="a", attempt=2)],
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert record.steps[0].result == {"name": "a", "attempt": 1}


def test_a_failure_after_a_kept_result_that_is_not_found_is_compensated(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(calls=calls, execute_script=["keep then failed"], find_outcome_answers=[None])

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, calls[-1]) == (SagaStatus.ROLLED_BACK, "compensate a")


def test_an_unknown_outcome_after_a_kept_result_that_is_not_found_needs_manual_intervention(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    step: FakeStep = FakeStep(
        calls=calls, execute_script=["keep then outcome unknown"], find_outcome_answers=[None]
    )

    record: SagaRecord = run(steps=[planned(step=step, key="a")], record_writer=record_writer, lock=lock)

    assert (record.status, step.compensate_calls, lock.held_by) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        0,
        SAGA_ID,
    )


def test_a_pivot_that_kept_a_result_and_failed_needs_manual_intervention(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(
            step=FakeStep(calls=calls, kind=StepKind.PIVOT, execute_script=["keep then failed"]), key="p"
        ),
    ]

    record: SagaRecord = run(steps=steps, record_writer=record_writer, lock=lock)

    assert record.steps[1].status is StepStatus.UNRESOLVED


class StepWithBuggyCompensation(FakeStep):
    def compensate(self, *, step_input: FakeInput, result: FakeResult) -> None:
        raise ValueError("bug in compensate")


def test_a_bug_during_compensation_leaves_that_step_compensating(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=StepWithBuggyCompensation(calls=calls), key="a"),
        planned(step=FakeStep(calls=calls, execute_script=[FAILED]), key="b"),
    ]

    with pytest.raises(expected_exception=ValueError):
        run(steps=steps, record_writer=record_writer, lock=lock)

    assert record_writer.saved is not None and record_writer.saved.steps[0].status is StepStatus.COMPENSATING


def failed_step_whose_compensation_fails(
    *, calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> SagaRecord:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(calls=calls), key="a"),
        planned(
            step=FakeStep(calls=calls, execute_script=["keep then failed"], compensation_script=[AMBIGUOUS]),
            key="b",
        ),
    ]
    return run(steps=steps, record_writer=record_writer, lock=lock)


def test_a_failed_step_that_kept_a_result_is_still_the_step_that_stopped_the_saga_after_its_compensation(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    record: SagaRecord = failed_step_whose_compensation_fails(
        calls=calls, record_writer=record_writer, lock=lock
    )

    assert record.stopped_at == "b"


def test_a_failed_compensation_keeps_the_error_that_failed_the_step(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    stopped: StepRecord = failed_step_whose_compensation_fails(
        calls=calls, record_writer=record_writer, lock=lock
    ).steps[1]

    assert (
        stopped.error and stopped.error.message,
        stopped.compensation_error and stopped.compensation_error.message,
    ) == ("no", "two found")


def refuse_to_start() -> None:
    raise FAILED


def run_saga_refused_before_start(
    *, calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    executor: SagaExecutor = SagaExecutor(
        record_writer=record_writer,
        lock=lock,
        runner=StepRunner(settings=SETTINGS, classifier=FakeClassifier(), sleeper=RecordingSleeper()),
        compensator=Compensator(settings=SETTINGS, classifier=FakeClassifier(), sleeper=RecordingSleeper()),
    )
    with pytest.raises(expected_exception=FakeError):
        executor.run(
            saga_id=SAGA_ID,
            plan=SagaPlan(steps=[planned(step=FakeStep(calls=calls), key="a")], lock_keys=LOCK_KEYS),
            check_before_start=refuse_to_start,
        )


def test_a_check_before_start_that_fails_releases_the_lock(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    run_saga_refused_before_start(calls=calls, record_writer=record_writer, lock=lock)

    assert lock.held_by is None


def test_a_check_before_start_that_fails_runs_no_step(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    run_saga_refused_before_start(calls=calls, record_writer=record_writer, lock=lock)

    assert calls == []


def test_a_check_before_start_that_fails_stores_no_record(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    run_saga_refused_before_start(calls=calls, record_writer=record_writer, lock=lock)

    assert record_writer.saved is None


def test_the_check_before_start_runs_under_the_lock(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    held_during_check: list[str | None] = []
    executor: SagaExecutor = SagaExecutor(
        record_writer=record_writer,
        lock=lock,
        runner=StepRunner(settings=SETTINGS, classifier=FakeClassifier(), sleeper=RecordingSleeper()),
        compensator=Compensator(settings=SETTINGS, classifier=FakeClassifier(), sleeper=RecordingSleeper()),
    )

    executor.run(
        saga_id=SAGA_ID,
        plan=SagaPlan(steps=[planned(step=FakeStep(calls=calls), key="a")], lock_keys=LOCK_KEYS),
        check_before_start=lambda: held_during_check.append(lock.held_by),
    )

    assert held_during_check == [SAGA_ID]


def test_a_saga_whose_lock_was_taken_over_before_it_started_does_not_start(
    calls: list[str], record_writer: InMemorySagaRecordWriter, lock: InMemorySagaLock
) -> None:
    def lose_the_lock() -> None:
        lock.held_by = "other-saga"

    with pytest.raises(expected_exception=ResourcesLockedError):
        run(
            steps=[planned(step=FakeStep(calls=calls), key="a")],
            record_writer=record_writer,
            lock=lock,
            check_before_start=lose_the_lock,
        )
    assert record_writer.saved is None


def test_a_kept_result_is_saved_before_the_step_ends(calls: list[str], lock: InMemorySagaLock) -> None:
    record_writer: FinalSaveFailingRecordWriter = FinalSaveFailingRecordWriter()

    with pytest.raises(expected_exception=ConnectionError):
        run(
            steps=[planned(step=FakeStep(calls=calls, execute_script=["keep then interrupt"]), key="a")],
            record_writer=record_writer,
            lock=lock,
        )

    assert record_writer.saved is not None and record_writer.saved.steps[0].result is not None
