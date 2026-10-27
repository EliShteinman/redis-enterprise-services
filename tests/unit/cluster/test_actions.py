from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.actions import ActionWaiter
from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.config.wait_settings import WaitSettings
from redis_enterprise_services.edge.models import ClusterCredentials, ClusterResponse
from redis_enterprise_services.exceptions.cluster import ClusterActionFailedError, ClusterActionTimeoutError

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
ACTION_UID: str = "c7d4bccf-9462-4924-8c8f-345bd94fe89c"
SHORT_WAIT: WaitSettings = WaitSettings(interval_seconds=0.001, timeout_seconds=0.01)


def waiter_answering(*, action: JsonValue) -> ActionWaiter:
    api: MagicMock = create_autospec(spec=ClusterApi, instance=True)
    api.send.return_value = ClusterResponse(status_code=200, headers={}, body=action, cluster_state_id=None)
    settings: Settings = load_settings()
    action_settings: ActionSettings = settings.action.model_copy(update={"wait": SHORT_WAIT})
    return ActionWaiter(api=api, settings=action_settings, cluster=settings.cluster)


def test_a_completed_action_ends_the_wait() -> None:
    waiter_answering(action={"status": "completed"}).wait(target=TARGET, action_uid=ACTION_UID)


@pytest.mark.parametrize(
    argnames="action",
    argvalues=[{"status": "failed"}, {"status": "cancelled"}, {"status": "aborted"}, {"progress": "100"}],
)
def test_an_action_that_ended_without_completing_fails_at_once(action: JsonValue) -> None:
    with pytest.raises(expected_exception=ClusterActionFailedError):
        waiter_answering(action=action).wait(target=TARGET, action_uid=ACTION_UID)


def test_a_running_action_times_out() -> None:
    with pytest.raises(expected_exception=ClusterActionTimeoutError):
        waiter_answering(action={"status": "running"}).wait(target=TARGET, action_uid=ACTION_UID)
