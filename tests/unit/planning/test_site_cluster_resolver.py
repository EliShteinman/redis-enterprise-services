import pytest
from pydantic import SecretStr

from redis_enterprise_services.config.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.cluster_inventory import (
    ClusterType,
    ConfiguredCluster,
    Environment,
)
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.exceptions.planning import NoMatchingClusterError
from redis_enterprise_services.planning.cluster_chooser import ClusterChooser
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.single_candidate_chooser import SingleCandidateChooser
from redis_enterprise_services.planning.site_cluster_resolver import SiteClusterResolver
from redis_enterprise_services.planning.site_placement import SitePlacement


def cluster(
    *,
    fqdn: str,
    cluster_type: ClusterType = "generic",
    environment: Environment = "PROD",
    network: str = "net-a",
    site: str = "ny",
) -> ConfiguredCluster:
    return ConfiguredCluster(
        fqdn=fqdn,
        network=network,
        environment=environment,
        site=site,
        type=cluster_type,
        api_url=f"https://{fqdn}:9443",
        credentials=ClusterCredentialsSettings(username="admin", password=SecretStr("secret")),
        default_user_password=SecretStr("default-user-secret"),
    )


def placement(*, requested_cluster: str = "generic") -> SitePlacement:
    return SitePlacement(environment="PROD", network="net-a", site="ny", cluster=requested_cluster)


class LastCandidateChooser(ClusterChooser):
    def choose(self, *, placement: SitePlacement, candidates: list[ConfiguredCluster]) -> ConfiguredCluster:
        return candidates[-1]


def resolver(*, clusters: list[ConfiguredCluster]) -> SiteClusterResolver:
    return SiteClusterResolver(
        directory=ClusterDirectory(clusters=clusters), chooser=SingleCandidateChooser()
    )


def test_a_generic_cluster_does_not_answer_a_request_for_its_fqdn() -> None:
    with pytest.raises(expected_exception=NoMatchingClusterError):
        resolver(clusters=[cluster(fqdn="orders.net-a")]).resolve(
            placement=placement(requested_cluster="orders.net-a")
        )


def test_a_cluster_requested_by_fqdn_must_be_dedicated_and_at_the_requested_site() -> None:
    wanted: ConfiguredCluster = cluster(fqdn="orders.net-a", cluster_type="dedicated")
    clusters: list[ConfiguredCluster] = [
        cluster(fqdn="orders.net-a", cluster_type="dedicated", environment="DEV"),
        cluster(fqdn="orders.net-a", cluster_type="dedicated", network="net-b"),
        cluster(fqdn="orders.net-a", cluster_type="dedicated", site="tlv"),
        cluster(fqdn="c1.net-a"),
        wanted,
    ]

    assert (
        resolver(clusters=clusters).resolve(placement=placement(requested_cluster="orders.net-a")) == wanted
    )


def test_a_generic_placement_takes_the_only_generic_cluster_at_the_site() -> None:
    generic: ConfiguredCluster = cluster(fqdn="c1.net-a")
    clusters: list[ConfiguredCluster] = [cluster(fqdn="orders.net-a", cluster_type="dedicated"), generic]

    assert resolver(clusters=clusters).resolve(placement=placement()) == generic


def test_a_generic_placement_leaves_the_choice_among_its_candidates_to_the_chooser() -> None:
    last: ConfiguredCluster = cluster(fqdn="c2.net-a")
    directory: ClusterDirectory = ClusterDirectory(clusters=[cluster(fqdn="c1.net-a"), last])

    chosen: ConfiguredCluster = SiteClusterResolver(
        directory=directory, chooser=LastCandidateChooser()
    ).resolve(placement=placement())

    assert chosen == last


@pytest.mark.parametrize(
    argnames="requested_placement",
    argvalues=[
        pytest.param(placement(), id="generic"),
        pytest.param(placement(requested_cluster="orders.net-a"), id="dedicated"),
    ],
)
def test_a_placement_without_a_configured_cluster_is_refused(requested_placement: SitePlacement) -> None:
    with pytest.raises(expected_exception=NoMatchingClusterError):
        resolver(clusters=[cluster(fqdn="c1.net-a", site="tlv")]).resolve(placement=requested_placement)


def test_several_generic_clusters_at_a_site_cannot_be_chosen_yet() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        resolver(clusters=[cluster(fqdn="c1.net-a"), cluster(fqdn="c2.net-a")]).resolve(placement=placement())


def test_the_single_candidate_chooser_refuses_an_empty_candidate_list() -> None:
    with pytest.raises(expected_exception=NoMatchingClusterError):
        SingleCandidateChooser().choose(placement=placement(), candidates=[])
