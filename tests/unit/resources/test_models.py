import pytest
from pydantic import SecretStr, ValidationError

from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.resources.models import CreateResourceInput
from redis_enterprise_services.users.models import NewUser


def test_a_step_input_keeps_only_the_address_of_a_target_with_credentials() -> None:
    target: ClusterTarget = ClusterTarget(
        network="local",
        api_url="https://cluster.local:9443",
        credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
    )

    step_input: CreateResourceInput[NewUser] = CreateResourceInput(
        cluster=target, spec=NewUser(name="app-user", password="Aa1!password", role_uids=[5])
    )

    assert type(step_input.cluster) is ClusterAddress


def test_a_step_input_cannot_be_changed_after_it_is_built() -> None:
    step_input: CreateResourceInput[NewUser] = CreateResourceInput(
        cluster=ClusterAddress(network="local", api_url="https://cluster.local:9443"),
        spec=NewUser(name="app-user", password="Aa1!password", role_uids=[5]),
    )

    with pytest.raises(expected_exception=ValidationError):
        step_input.cluster = ClusterAddress(network="other", api_url="https://other:9443")
