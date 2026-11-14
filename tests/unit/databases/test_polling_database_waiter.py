from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster.status_polling import StatusPolling
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.config.wait_settings import WaitSettings
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsReader
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.databases.polling_database_waiter import PollingDatabaseWaiter
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    DatabaseActivationTimeoutError,
    DatabaseCreationFailedError,
    UnreadableClusterResponseError,
)
from redis_enterprise_services.timing.clock import MonotonicClock
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.timing.sleeper import SystemSleeper

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)


@pytest.fixture
def fields_reader() -> MagicMock:
    return create_autospec(spec=DatabaseFieldsReader, instance=True)


@pytest.fixture
def waiter(fields_reader: MagicMock) -> PollingDatabaseWaiter:
    settings: Settings = load_settings()
    short_wait: WaitSettings = WaitSettings(poll_interval_seconds=0.001, timeout_seconds=0.05)
    database_settings: DatabaseSettings = settings.database.model_copy(update={"wait": short_wait})
    read_again_polling: ReadAgainPolling = ReadAgainPolling(
        deadline_polling=DeadlinePolling(clock=MonotonicClock(), sleeper=SystemSleeper()),
        transient_error_codes=settings.cluster_api.transient_error_codes,
    )
    return PollingDatabaseWaiter(
        fields_reader=fields_reader,
        read_again_polling=read_again_polling,
        status_polling=StatusPolling(
            read_again_polling=read_again_polling, status_field=settings.cluster_api.fields.status
        ),
        settings=database_settings,
    )


def test_a_deleted_database_is_gone_once_it_answers_404(
    fields_reader: MagicMock, waiter: PollingDatabaseWaiter
) -> None:
    fields_reader.read.side_effect = ClusterRejectedRequestError(
        message="gone", cluster_status_code=404, cluster_error_code="db_not_exist"
    )

    waiter.wait_for_pending_deletion(target=TARGET, uid=11, action_uid=None)

    fields_reader.read.assert_called_once()


def test_a_rejection_not_safe_to_read_again_while_waiting_for_a_delete_is_raised(
    fields_reader: MagicMock, waiter: PollingDatabaseWaiter
) -> None:
    fields_reader.read.side_effect = ClusterRejectedRequestError(
        message="no", cluster_status_code=403, cluster_error_code=None
    )

    with pytest.raises(expected_exception=ClusterRejectedRequestError):
        waiter.wait_for_pending_deletion(target=TARGET, uid=11, action_uid=None)


def test_a_cluster_failure_while_waiting_for_a_delete_is_read_again(
    fields_reader: MagicMock, waiter: PollingDatabaseWaiter
) -> None:
    fields_reader.read.side_effect = [
        ClusterRejectedRequestError(message="failing over", cluster_status_code=503, cluster_error_code=None),
        ClusterRejectedRequestError(
            message="gone", cluster_status_code=404, cluster_error_code="db_not_exist"
        ),
    ]

    waiter.wait_for_pending_deletion(target=TARGET, uid=11, action_uid=None)

    assert fields_reader.read.call_count == 2


def test_a_database_whose_creation_failed_stops_the_wait(
    fields_reader: MagicMock, waiter: PollingDatabaseWaiter
) -> None:
    fields_reader.read.return_value = DatabaseFieldsSnapshot(
        values={"status": "creation-failed"}, cluster_state_id=1
    )

    with pytest.raises(expected_exception=DatabaseCreationFailedError):
        waiter.wait_until_active(target=TARGET, uid=11)


def test_a_database_answer_without_a_status_is_unreadable(
    fields_reader: MagicMock, waiter: PollingDatabaseWaiter
) -> None:
    fields_reader.read.return_value = DatabaseFieldsSnapshot(values={}, cluster_state_id=1)

    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        waiter.wait_until_active(target=TARGET, uid=11)


def test_a_database_that_stays_pending_times_out(
    fields_reader: MagicMock, waiter: PollingDatabaseWaiter
) -> None:
    fields_reader.read.return_value = DatabaseFieldsSnapshot(values={"status": "pending"}, cluster_state_id=1)

    with pytest.raises(expected_exception=DatabaseActivationTimeoutError):
        waiter.wait_until_active(target=TARGET, uid=11)


def test_a_database_that_becomes_active_ends_the_wait(
    fields_reader: MagicMock, waiter: PollingDatabaseWaiter
) -> None:
    fields_reader.read.side_effect = [
        DatabaseFieldsSnapshot(values={"status": "pending"}, cluster_state_id=1),
        DatabaseFieldsSnapshot(values={"status": "active"}, cluster_state_id=1),
    ]

    waiter.wait_until_active(target=TARGET, uid=11)

    assert fields_reader.read.call_count == 2


def test_an_active_database_returns_the_whole_database_last_read(
    fields_reader: MagicMock, waiter: PollingDatabaseWaiter
) -> None:
    active: DatabaseFieldsSnapshot = DatabaseFieldsSnapshot(
        values={"status": "active", "uid": 11, "port": 12000}, cluster_state_id=4
    )
    fields_reader.read.return_value = active

    assert waiter.wait_until_active(target=TARGET, uid=11) == active
