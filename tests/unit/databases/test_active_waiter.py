from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.config.wait_settings import WaitSettings
from redis_enterprise_services.databases.active_waiter import DatabaseActiveWaiter
from redis_enterprise_services.databases.fields_store import DatabaseFieldsReader
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    DatabaseCreationFailedError,
    UnreadableClusterResponseError,
)

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


@pytest.fixture
def fields() -> MagicMock:
    return create_autospec(spec=DatabaseFieldsReader, instance=True)


@pytest.fixture
def waiter(fields: MagicMock) -> DatabaseActiveWaiter:
    settings: Settings = load_settings()
    short_wait: WaitSettings = WaitSettings(poll_interval_seconds=0.001, timeout_seconds=0.05)
    database: DatabaseSettings = settings.database.model_copy(update={"wait": short_wait})
    return DatabaseActiveWaiter(fields=fields, settings=database, cluster_api=settings.cluster_api)


def test_a_deleted_database_is_gone_once_it_answers_404(
    fields: MagicMock, waiter: DatabaseActiveWaiter
) -> None:
    fields.get_fields.side_effect = ClusterRejectedRequestError(
        message="gone", cluster_status_code=404, cluster_error_code="db_not_exist"
    )

    waiter.wait_deleted(target=TARGET, uid=11, action_uid=None)

    fields.get_fields.assert_called_once()


def test_another_error_while_waiting_for_a_delete_is_raised(
    fields: MagicMock, waiter: DatabaseActiveWaiter
) -> None:
    fields.get_fields.side_effect = ClusterRejectedRequestError(
        message="no", cluster_status_code=403, cluster_error_code=None
    )

    with pytest.raises(expected_exception=ClusterRejectedRequestError):
        waiter.wait_deleted(target=TARGET, uid=11, action_uid=None)


def test_a_cluster_failure_while_waiting_for_a_delete_is_read_again(
    fields: MagicMock, waiter: DatabaseActiveWaiter
) -> None:
    fields.get_fields.side_effect = [
        ClusterRejectedRequestError(message="failing over", cluster_status_code=503, cluster_error_code=None),
        ClusterRejectedRequestError(
            message="gone", cluster_status_code=404, cluster_error_code="db_not_exist"
        ),
    ]

    waiter.wait_deleted(target=TARGET, uid=11, action_uid=None)

    assert fields.get_fields.call_count == 2


def test_a_database_whose_creation_failed_stops_the_wait(
    fields: MagicMock, waiter: DatabaseActiveWaiter
) -> None:
    fields.get_fields.return_value = DatabaseFields(values={"status": "creation-failed"}, cluster_state_id=1)

    with pytest.raises(expected_exception=DatabaseCreationFailedError):
        waiter.wait(target=TARGET, uid=11)


def test_a_database_answer_without_a_status_is_unreadable(
    fields: MagicMock, waiter: DatabaseActiveWaiter
) -> None:
    fields.get_fields.return_value = DatabaseFields(values={}, cluster_state_id=1)

    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        waiter.wait(target=TARGET, uid=11)
