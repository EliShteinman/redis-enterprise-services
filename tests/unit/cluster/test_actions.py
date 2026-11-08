from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.actions import ActionWaiter
from redis_enterprise_services.cluster.caller import ClusterCaller
from redis_enterprise_services.cluster.models import ClusterAnswer, ClusterTarget
from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.config.wait_settings import WaitSettings
from redis_enterprise_services.connection.models import ClusterCredentials
from redis_enterprise_services.exceptions.cluster import (
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    UnreadableAnswerError,
)

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
ACTION_UID: str = "c7d4bccf-9462-4924-8c8f-345bd94fe89c"
SHORT_WAIT: WaitSettings = WaitSettings(interval_seconds=0.001, timeout_seconds=0.01)


def api_answering(*, action: JsonValue) -> MagicMock:
    api: MagicMock = create_autospec(spec=ClusterCaller, instance=True)
    api.send.return_value = ClusterAnswer(body=action, cluster_state_id=None)
    return api


def waiter_answering(*, action: JsonValue, api: MagicMock | None = None) -> ActionWaiter:
    settings: Settings = load_settings()
    action_settings: ActionSettings = settings.action.model_copy(update={"wait": SHORT_WAIT})
    return ActionWaiter(
        api=api or api_answering(action=action), settings=action_settings, cluster=settings.cluster
    )


def test_a_completed_action_ends_the_wait_after_asking_for_that_action() -> None:
    api: MagicMock = api_answering(action={"status": "completed"})

    waiter_answering(action={"status": "completed"}, api=api).wait(target=TARGET, action_uid=ACTION_UID)

    assert api.send.call_args.kwargs["path"].endswith(ACTION_UID)


@pytest.mark.parametrize(
    argnames="action",
    argvalues=[{"status": "failed"}, {"status": "cancelled"}, {"status": "aborted"}],
)
def test_an_action_that_ended_without_completing_fails_at_once(action: JsonValue) -> None:
    with pytest.raises(expected_exception=ClusterActionFailedError):
        waiter_answering(action=action).wait(target=TARGET, action_uid=ACTION_UID)


def test_a_running_action_times_out() -> None:
    with pytest.raises(expected_exception=ClusterActionTimeoutError):
        waiter_answering(action={"status": "running"}).wait(target=TARGET, action_uid=ACTION_UID)


def test_an_action_answer_without_a_status_is_unreadable() -> None:
    with pytest.raises(expected_exception=UnreadableAnswerError):
        waiter_answering(action={"progress": "100"}).wait(target=TARGET, action_uid=ACTION_UID)
