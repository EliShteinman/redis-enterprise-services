from collections.abc import Callable

import pytest
from pydantic import BaseModel

from redis_enterprise_services.config.saga_settings import RetrySettings, SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.saga import DatabaseLockedError, InvalidPlanError
from redis_enterprise_services.saga.compensator import Compensator
from redis_enterprise_services.saga.context import SagaContext
from redis_enterprise_services.saga.executor import SagaExecutor
from redis_enterprise_services.saga.failure import Failure, FailureClassifier
from redis_enterprise_services.saga.kind import StepKind
from redis_enterprise_services.saga.lock import DatabaseLock
from redis_enterprise_services.saga.models import SagaRecord, SagaStatus, StepStatus
from redis_enterprise_services.saga.plan import SagaPlan
from redis_enterprise_services.saga.planned_step import PlannedStep
from redis_enterprise_services.saga.result import KeepResult
from redis_enterprise_services.saga.saga_step import SagaStep
from redis_enterprise_services.saga.state import SagaStateRepository
from redis_enterprise_services.saga.step_runner import StepRunner

SAGA_ID: str = "trace-1"
LOCK_KEYS: list[str] = ["cluster1/db1"]
SETTINGS: SagaSettings = SagaSettings(
    step_retry=RetrySettings(attempts=3, backoff_seconds=0),
    compensation_retry=RetrySettings(attempts=2, backoff_seconds=0),
)


class FakeError(RedisEnterpriseServicesError):
    def __init__(self, *, message: str, failure: Failure) -> None:
        super().__init__(message=message)
        self.failure: Failure = failure


class FakeClassifier(FailureClassifier):
    def classify(self, *, error: RedisEnterpriseServicesError) -> Failure:
        return error.failure if isinstance(error, FakeError) else Failure.FAILED

    def classify_lookup(self, *, error: RedisEnterpriseServicesError) -> Failure:
        return self.classify(error=error)


BUSY: FakeError = FakeError(message="busy", failure=Failure.TRANSIENT)
REJECTED: FakeError = FakeError(message="no", failure=Failure.FAILED)
UNKNOWN: FakeError = FakeError(message="timeout", failure=Failure.UNKNOWN)
AMBIGUOUS: FakeError = FakeError(message="two found", failure=Failure.MANUAL)

type Action = str | RedisEnterpriseServicesError


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
        journal: list[str],
        kind: StepKind = StepKind.COMPENSATABLE,
        executions: list[Action] | None = None,
        outcomes: list[FakeResult | RedisEnterpriseServicesError | None] | None = None,
        compensations: list[RedisEnterpriseServicesError | None] | None = None,
    ) -> None:
        self._journal: list[str] = journal
        self._kind: StepKind = kind
        self._executions: list[Action] = executions or ["keep"]
        self._outcomes: list[FakeResult | RedisEnterpriseServicesError | None] = outcomes or []
        self._compensations: list[RedisEnterpriseServicesError | None] = compensations or [None]
        self.executed: int = 0

    @property
    def kind(self) -> StepKind:
        return self._kind

    def execute(self, *, step_input: FakeInput, keep_result: KeepResult[FakeResult]) -> None:
        action: Action = self._executions[min(self.executed, len(self._executions) - 1)]
        self.executed += 1
        self._journal.append(f"execute {step_input.name}")
        if isinstance(action, RedisEnterpriseServicesError):
            raise action
        if action == "interrupt":
            raise SystemExit(1)
        keep_result(FakeResult(name=step_input.name, attempt=self.executed))
        if action == "keep then busy":
            raise BUSY
        if action == "keep then rejected":
            raise REJECTED

    def find_outcome(self, *, step_input: FakeInput, kept: FakeResult | None) -> FakeResult | None:
        outcome: FakeResult | RedisEnterpriseServicesError | None = (
            self._outcomes.pop(0) if self._outcomes else None
        )
        if isinstance(outcome, RedisEnterpriseServicesError):
            raise outcome
        return outcome

    def compensate(self, *, step_input: FakeInput, result: FakeResult) -> None:
        self._journal.append(f"compensate {step_input.name}")
        error: RedisEnterpriseServicesError | None = self._compensations[0]
        if error is not None:
            raise error


class MemoryState(SagaStateRepository):
    def __init__(self, *, broken: bool = False) -> None:
        self.saved: SagaRecord | None = None
        self.finished: bool = False
        self._broken: bool = broken

    def save(self, *, record: SagaRecord) -> None:
        if self._broken:
            raise ConnectionError("state store is down")
        self.saved = record.model_copy(deep=True)

    def finish(self, *, record: SagaRecord) -> None:
        self.saved = record.model_copy(deep=True)
        self.finished = True


class MemoryLock(DatabaseLock):
    def __init__(self, *, held_by: str | None = None) -> None:
        self.held_by: str | None = held_by

    def acquire(self, *, keys: list[str], owner: str) -> None:
        if self.held_by not in (None, owner):
            raise DatabaseLockedError(message=f"{keys} locked by {self.held_by}")
        self.held_by = owner

    def release(self, *, keys: list[str], owner: str) -> None:
        if self.held_by == owner:
            self.held_by = None


def planned(
    *, step: FakeStep, name: str, build: Callable[[SagaContext], FakeInput] | None = None
) -> PlannedStep[FakeInput, FakeResult]:
    return PlannedStep(key=name, step=step, build_input=build or (lambda context: FakeInput(name=name)))


@pytest.fixture
def journal() -> list[str]:
    return []


@pytest.fixture
def state() -> MemoryState:
    return MemoryState()


@pytest.fixture
def lock() -> MemoryLock:
    return MemoryLock()


def run(
    *, steps: list[PlannedStep[FakeInput, FakeResult]], state: MemoryState, lock: MemoryLock
) -> SagaRecord:
    executor: SagaExecutor = SagaExecutor(
        state=state,
        lock=lock,
        runner=StepRunner(settings=SETTINGS, classifier=FakeClassifier()),
        compensator=Compensator(settings=SETTINGS),
    )
    return executor.run(saga_id=SAGA_ID, plan=SagaPlan(steps=list(steps), lock_keys=LOCK_KEYS))


def statuses(record: SagaRecord) -> list[StepStatus]:
    return [step.status for step in record.steps]


def test_all_steps_done_succeeds_and_releases_the_lock(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    record: SagaRecord = run(
        steps=[planned(step=FakeStep(journal=journal), name=name) for name in ("a", "b")],
        state=state,
        lock=lock,
    )

    assert (record.status, statuses(record), lock.held_by) == (
        SagaStatus.SUCCEEDED,
        [StepStatus.DONE, StepStatus.DONE],
        None,
    )


def test_a_failed_step_compensates_the_earlier_steps_in_reverse(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal), name="b"),
        planned(step=FakeStep(journal=journal, executions=[REJECTED]), name="c"),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert (record.status, journal[-2:]) == (SagaStatus.ROLLED_BACK, ["compensate b", "compensate a"])


def test_a_transient_error_is_retried(journal: list[str], state: MemoryState, lock: MemoryLock) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=[BUSY, "keep"])

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert (record.status, step.executed) == (SagaStatus.SUCCEEDED, 2)


def test_an_unknown_outcome_that_is_found_is_done_without_running_again(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(
        journal=journal, executions=[UNKNOWN], outcomes=[FakeResult(name="a", attempt=0)]
    )

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert (record.status, step.executed, record.steps[0].obtained_by) == (SagaStatus.SUCCEEDED, 1, "found")


def test_an_unknown_outcome_that_is_not_found_runs_the_step_again(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=[UNKNOWN, "keep"], outcomes=[None])

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert (record.status, step.executed) == (SagaStatus.SUCCEEDED, 2)


def test_an_ambiguous_outcome_stops_for_manual_intervention_and_keeps_the_lock(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(
            step=FakeStep(journal=journal, executions=[UNKNOWN], outcomes=[AMBIGUOUS]),
            name="b",
        ),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert (record.status, "compensate a" in journal, lock.held_by) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        False,
        SAGA_ID,
    )


def test_a_step_that_fails_for_manual_intervention_runs_once(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=[AMBIGUOUS])

    run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert step.executed == 1


def test_a_step_that_fails_for_manual_intervention_is_unresolved(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal, executions=[AMBIGUOUS]), name="b"),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert statuses(record) == [StepStatus.DONE, StepStatus.UNRESOLVED]


def test_a_check_that_fails_for_a_known_reason_compensates_the_earlier_steps(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal, executions=[UNKNOWN], outcomes=[REJECTED]), name="b"),
    ]

    run(steps=steps, state=state, lock=lock)

    assert journal[-1] == "compensate a"


def test_a_failed_compensation_still_compensates_the_others_and_needs_manual_intervention(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal, compensations=[REJECTED]), name="b"),
        planned(step=FakeStep(journal=journal, executions=[REJECTED]), name="c"),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert (record.status, statuses(record)[:2], lock.held_by) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        [StepStatus.COMPENSATED, StepStatus.COMPENSATION_FAILED],
        SAGA_ID,
    )


def test_a_failure_after_the_pivot_is_not_compensated(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal, kind=StepKind.PIVOT), name="pivot"),
        planned(step=FakeStep(journal=journal, kind=StepKind.RETRIABLE, executions=[REJECTED]), name="after"),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert (record.status, [entry for entry in journal if entry.startswith("compensate")]) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        [],
    )


def test_a_step_that_kept_a_result_before_failing_is_compensated(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=["keep then busy"])

    run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert journal[-1] == "compensate a"


def test_a_transient_error_after_a_kept_result_is_retried(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=["keep then busy", "keep"])

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert (record.status, step.executed) == (SagaStatus.SUCCEEDED, 2)


def test_a_known_failure_after_a_kept_result_that_is_not_found_is_not_run_again(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=["keep then rejected", "keep"], outcomes=[None])

    run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert step.executed == 1


def test_an_outcome_that_stays_unknown_needs_manual_intervention(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=[UNKNOWN], outcomes=[UNKNOWN, UNKNOWN, UNKNOWN])

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert (record.status, lock.held_by) == (SagaStatus.REQUIRES_MANUAL_INTERVENTION, SAGA_ID)


def test_an_interrupted_saga_keeps_the_lock(journal: list[str], state: MemoryState, lock: MemoryLock) -> None:
    interrupted: FakeStep = FakeStep(journal=journal, executions=["interrupt"])

    with pytest.raises(expected_exception=SystemExit):
        run(
            steps=[planned(step=interrupted, name="a")],
            state=state,
            lock=lock,
        )

    assert (lock.held_by, state.saved is not None and state.saved.steps[0].status) == (
        SAGA_ID,
        StepStatus.UNRESOLVED,
    )


def test_a_saga_that_cannot_save_its_first_record_releases_the_lock(
    journal: list[str], lock: MemoryLock
) -> None:
    with pytest.raises(expected_exception=ConnectionError):
        run(
            steps=[planned(step=FakeStep(journal=journal), name="a")],
            state=MemoryState(broken=True),
            lock=lock,
        )

    assert (lock.held_by, journal) == (None, [])


def test_a_later_step_builds_its_input_from_an_earlier_result(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    def child_input(context: SagaContext) -> FakeInput:
        return FakeInput(name="b", parent=context.result_of(key="a", result_type=FakeResult).name)

    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal), name="b", build=child_input),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert record.steps[1].step_input == {"name": "b", "parent": "a"}


def test_a_locked_database_runs_no_step(journal: list[str], state: MemoryState) -> None:
    with pytest.raises(expected_exception=DatabaseLockedError):
        run(
            steps=[planned(step=FakeStep(journal=journal), name="a")],
            state=state,
            lock=MemoryLock(held_by="other"),
        )

    assert journal == []


def test_an_unexpected_error_needs_manual_intervention_and_keeps_the_lock(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    def broken_input(context: SagaContext) -> FakeInput:
        raise ValueError("bug")

    with pytest.raises(expected_exception=ValueError):
        run(
            steps=[planned(step=FakeStep(journal=journal), name="a", build=broken_input)],
            state=state,
            lock=lock,
        )

    assert (state.saved is not None and state.saved.status, lock.held_by) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        SAGA_ID,
    )


def test_a_compensatable_step_after_the_pivot_is_refused(journal: list[str]) -> None:
    with pytest.raises(expected_exception=InvalidPlanError):
        SagaPlan(
            steps=[
                planned(step=FakeStep(journal=journal, kind=StepKind.PIVOT), name="pivot"),
                planned(step=FakeStep(journal=journal), name="a"),
            ],
            lock_keys=LOCK_KEYS,
        )


def test_a_failure_after_a_retriable_step_without_a_pivot_is_not_compensated(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal, kind=StepKind.RETRIABLE), name="b"),
        planned(step=FakeStep(journal=journal, kind=StepKind.RETRIABLE, executions=[REJECTED]), name="c"),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert (record.status, journal[-1]) == (SagaStatus.REQUIRES_MANUAL_INTERVENTION, "execute c")


def test_a_first_retriable_step_that_fails_compensates_the_steps_before_it(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal, kind=StepKind.RETRIABLE, executions=[REJECTED]), name="b"),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert statuses(record)[0] is StepStatus.COMPENSATED


def test_repeated_step_keys_are_refused(journal: list[str]) -> None:
    with pytest.raises(expected_exception=InvalidPlanError):
        SagaPlan(
            steps=[
                planned(step=FakeStep(journal=journal), name="a"),
                planned(step=FakeStep(journal=journal), name="a"),
            ],
            lock_keys=LOCK_KEYS,
        )


def test_a_missing_earlier_result_fails_the_step_and_compensates_the_rest(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    def needs_missing(context: SagaContext) -> FakeInput:
        return FakeInput(name="b", parent=context.result_of(key="missing", result_type=FakeResult).name)

    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal), name="b", build=needs_missing),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert (record.status, journal[-1]) == (SagaStatus.ROLLED_BACK, "compensate a")


def test_a_step_that_stops_the_saga_is_marked_unresolved(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=[UNKNOWN], outcomes=[AMBIGUOUS])

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert record.steps[0].status is StepStatus.UNRESOLVED


class FinishFailingState(MemoryState):
    def finish(self, *, record: SagaRecord) -> None:
        raise ConnectionError("state store is down")


def test_a_succeeded_saga_releases_the_lock_even_when_the_last_save_fails(
    journal: list[str], lock: MemoryLock
) -> None:
    with pytest.raises(expected_exception=ConnectionError):
        run(steps=[planned(step=FakeStep(journal=journal), name="a")], state=FinishFailingState(), lock=lock)

    assert lock.held_by is None


def test_a_known_failure_after_an_unknown_outcome_is_checked_again(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(
        journal=journal, executions=[UNKNOWN, REJECTED], outcomes=[None, FakeResult(name="a", attempt=1)]
    )

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert (record.status, record.steps[0].obtained_by) == (SagaStatus.SUCCEEDED, "found")


def test_a_known_failure_after_an_unknown_outcome_that_is_not_found_needs_manual_intervention(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=[UNKNOWN, REJECTED], outcomes=[None, None])

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert (record.status, lock.held_by) == (SagaStatus.REQUIRES_MANUAL_INTERVENTION, SAGA_ID)


def test_a_plan_without_a_lock_is_refused(journal: list[str]) -> None:
    with pytest.raises(expected_exception=InvalidPlanError):
        SagaPlan(steps=[planned(step=FakeStep(journal=journal), name="a")], lock_keys=[])


def test_a_failure_after_a_kept_result_lets_the_step_check_what_happened(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(
        journal=journal, executions=["keep then rejected"], outcomes=[FakeResult(name="a", attempt=1)]
    )

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert (record.status, step.executed) == (SagaStatus.SUCCEEDED, 1)


def test_only_the_first_kept_result_of_a_step_is_recorded(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(
        journal=journal, executions=["keep then rejected"], outcomes=[FakeResult(name="a", attempt=2)]
    )

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert record.steps[0].result == {"name": "a", "attempt": 1}


def test_a_failure_after_a_kept_result_that_did_not_happen_is_compensated(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    step: FakeStep = FakeStep(journal=journal, executions=["keep then rejected"], outcomes=[None])

    record: SagaRecord = run(steps=[planned(step=step, name="a")], state=state, lock=lock)

    assert (record.status, journal[-1]) == (SagaStatus.ROLLED_BACK, "compensate a")


def test_a_pivot_that_kept_a_result_and_failed_needs_manual_intervention(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=FakeStep(journal=journal), name="a"),
        planned(
            step=FakeStep(journal=journal, kind=StepKind.PIVOT, executions=["keep then rejected"]), name="p"
        ),
    ]

    record: SagaRecord = run(steps=steps, state=state, lock=lock)

    assert record.steps[1].status is StepStatus.UNRESOLVED


class BrokenCompensation(FakeStep):
    def compensate(self, *, step_input: FakeInput, result: FakeResult) -> None:
        raise ValueError("bug in compensate")


def test_a_bug_during_compensation_leaves_that_step_compensating(
    journal: list[str], state: MemoryState, lock: MemoryLock
) -> None:
    steps: list[PlannedStep[FakeInput, FakeResult]] = [
        planned(step=BrokenCompensation(journal=journal), name="a"),
        planned(step=FakeStep(journal=journal, executions=[REJECTED]), name="b"),
    ]

    with pytest.raises(expected_exception=ValueError):
        run(steps=steps, state=state, lock=lock)

    assert state.saved is not None and state.saved.steps[0].status is StepStatus.COMPENSATING
