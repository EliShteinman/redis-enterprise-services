from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster.polling_action_waiter import PollingActionWaiter
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.config.wait_settings import WaitSettings
from redis_enterprise_services.exceptions.cluster import (
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    ClusterRejectedRequestError,
    UnreadableClusterResponseError,
)
from redis_enterprise_services.exceptions.edge import EdgeOutcomeUnknownError, EdgeRejectedResponseError
from redis_enterprise_services.timing.clock import Clock
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.timing.sleeper import Sleeper

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
ACTION_UID: str = "c7d4bccf-9462-4924-8c8f-345bd94fe89c"
SHORT_WAIT: WaitSettings = WaitSettings(poll_interval_seconds=1, timeout_seconds=10)


class SimulatedTime(Clock, Sleeper):
    def __init__(self) -> None:
        self._now: float = 0.0

    def monotonic_seconds(self) -> float:
        return self._now

    def sleep(self, *, seconds: float) -> None:
        self._now += seconds


def cluster_api_caller_answering(*, action_body: JsonValue) -> MagicMock:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.return_value = SuccessfulClusterResponse(body=action_body, cluster_state_id=None)
    return api


def waiter(*, cluster_api_caller: MagicMock) -> PollingActionWaiter:
    settings: Settings = load_settings()
    action_settings: ActionSettings = settings.action.model_copy(update={"wait": SHORT_WAIT})
    simulated_time: SimulatedTime = SimulatedTime()
    return PollingActionWaiter(
        cluster_api_caller=cluster_api_caller,
        read_again_polling=ReadAgainPolling(
            deadline_polling=DeadlinePolling(clock=simulated_time, sleeper=simulated_time),
            transient_error_codes=settings.cluster_api.transient_error_codes,
        ),
        settings=action_settings,
        cluster_api_settings=settings.cluster_api,
    )


def waiter_answering(*, action_body: JsonValue) -> PollingActionWaiter:
    return waiter(cluster_api_caller=cluster_api_caller_answering(action_body=action_body))


def test_a_completed_action_ends_the_wait_after_asking_for_that_action() -> None:
    api: MagicMock = cluster_api_caller_answering(action_body={"status": "completed"})

    waiter(cluster_api_caller=api).wait_until_completed(target=TARGET, action_uid=ACTION_UID)

    assert api.send.call_args.kwargs["path"].endswith(ACTION_UID)


def test_an_unknown_relay_outcome_while_reading_the_action_is_read_again() -> None:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.side_effect = [
        EdgeOutcomeUnknownError(message="relay timed out"),
        SuccessfulClusterResponse(body={"status": "completed"}, cluster_state_id=None),
    ]

    waiter(cluster_api_caller=api).wait_until_completed(target=TARGET, action_uid=ACTION_UID)

    assert api.send.call_count == 2


@pytest.mark.parametrize(
    argnames="transient_rejection",
    argvalues=[
        ClusterRejectedRequestError(message="busy", cluster_status_code=409, cluster_error_code="busy"),
        ClusterRejectedRequestError(message="failing over", cluster_status_code=503, cluster_error_code=None),
    ],
)
def test_a_transient_cluster_rejection_while_reading_the_action_is_read_again(
    transient_rejection: ClusterRejectedRequestError,
) -> None:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.side_effect = [
        transient_rejection,
        SuccessfulClusterResponse(body={"status": "completed"}, cluster_state_id=None),
    ]

    waiter(cluster_api_caller=api).wait_until_completed(target=TARGET, action_uid=ACTION_UID)

    assert api.send.call_count == 2


def test_a_permanent_cluster_rejection_while_reading_the_action_fails_at_once() -> None:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.side_effect = ClusterRejectedRequestError(
        message="not found", cluster_status_code=404, cluster_error_code=None
    )

    with pytest.raises(expected_exception=ClusterRejectedRequestError):
        waiter(cluster_api_caller=api).wait_until_completed(target=TARGET, action_uid=ACTION_UID)


def test_a_relay_rejected_action_response_fails_at_once() -> None:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.side_effect = EdgeRejectedResponseError(message="schema", cluster_status_code=200)

    with pytest.raises(expected_exception=EdgeRejectedResponseError):
        waiter(cluster_api_caller=api).wait_until_completed(target=TARGET, action_uid=ACTION_UID)


@pytest.mark.parametrize(
    argnames="action_body",
    argvalues=[{"status": "failed"}, {"status": "cancelled"}, {"status": "aborted"}],
)
def test_an_action_that_ended_without_completing_fails_at_once(action_body: JsonValue) -> None:
    with pytest.raises(expected_exception=ClusterActionFailedError):
        waiter_answering(action_body=action_body).wait_until_completed(target=TARGET, action_uid=ACTION_UID)


def test_a_running_action_times_out() -> None:
    with pytest.raises(expected_exception=ClusterActionTimeoutError):
        waiter_answering(action_body={"status": "running"}).wait_until_completed(
            target=TARGET, action_uid=ACTION_UID
        )


def test_an_action_answer_without_a_status_is_unreadable() -> None:
    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        waiter_answering(action_body={"progress": "100"}).wait_until_completed(
            target=TARGET, action_uid=ACTION_UID
        )


def test_a_wait_in_which_no_read_succeeded_reports_the_last_read_error() -> None:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.side_effect = EdgeOutcomeUnknownError(message="relay timed out")

    with pytest.raises(expected_exception=EdgeOutcomeUnknownError):
        waiter(cluster_api_caller=api).wait_until_completed(target=TARGET, action_uid=ACTION_UID)


def test_a_wait_with_a_read_that_succeeded_still_times_out() -> None:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    running: SuccessfulClusterResponse = SuccessfulClusterResponse(
        body={"status": "running"}, cluster_state_id=None
    )
    api.send.side_effect = [running, *([EdgeOutcomeUnknownError(message="relay timed out")] * 10)]

    with pytest.raises(expected_exception=ClusterActionTimeoutError):
        waiter(cluster_api_caller=api).wait_until_completed(target=TARGET, action_uid=ACTION_UID)
