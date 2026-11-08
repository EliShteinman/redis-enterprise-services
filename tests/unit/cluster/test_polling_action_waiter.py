from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster.polling_action_waiter import PollingActionWaiter
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

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
ACTION_UID: str = "c7d4bccf-9462-4924-8c8f-345bd94fe89c"
SHORT_WAIT: WaitSettings = WaitSettings(poll_interval_seconds=0.001, timeout_seconds=0.01)


def cluster_api_caller_answering(*, action_body: JsonValue) -> MagicMock:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.return_value = SuccessfulClusterResponse(body=action_body, cluster_state_id=None)
    return api


def waiter(*, cluster_api_caller: MagicMock) -> PollingActionWaiter:
    settings: Settings = load_settings()
    action_settings: ActionSettings = settings.action.model_copy(update={"wait": SHORT_WAIT})
    return PollingActionWaiter(
        cluster_api_caller=cluster_api_caller,
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
