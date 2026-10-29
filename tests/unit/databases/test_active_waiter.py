from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.connection.models import ClusterCredentials
from redis_enterprise_services.databases.active_waiter import DatabaseActiveWaiter
from redis_enterprise_services.databases.fields_store import DatabaseFieldsReader
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.exceptions.cluster import ClusterRequestError, DatabaseCreationFailedError

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
    return DatabaseActiveWaiter(fields=fields, settings=settings.database, cluster=settings.cluster)


def test_a_deleted_database_is_gone_once_it_answers_404(
    fields: MagicMock, waiter: DatabaseActiveWaiter
) -> None:
    fields.get_fields.side_effect = ClusterRequestError(
        message="gone", cluster_status_code=404, error_code="db_not_exist"
    )

    waiter.wait_deleted(target=TARGET, uid=11, action_uid=None)

    fields.get_fields.assert_called_once()


def test_another_error_while_waiting_for_a_delete_is_raised(
    fields: MagicMock, waiter: DatabaseActiveWaiter
) -> None:
    fields.get_fields.side_effect = ClusterRequestError(
        message="no", cluster_status_code=500, error_code=None
    )

    with pytest.raises(expected_exception=ClusterRequestError):
        waiter.wait_deleted(target=TARGET, uid=11, action_uid=None)


def test_a_database_whose_creation_failed_stops_the_wait(
    fields: MagicMock, waiter: DatabaseActiveWaiter
) -> None:
    fields.get_fields.return_value = DatabaseFields(values={"status": "creation-failed"}, cluster_state_id=1)

    with pytest.raises(expected_exception=DatabaseCreationFailedError):
        waiter.wait(target=TARGET, uid=11)
