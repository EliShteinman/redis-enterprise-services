import pytest

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
    *, name: str, cluster_type: ClusterType = "generic", environment: Environment = "PROD", site: str = "dc1"
) -> ConfiguredCluster:
    return ConfiguredCluster(
        name=name,
        network="net-a",
        environment=environment,
        site=site,
        type=cluster_type,
        api_url=f"https://{name}:9443",
    )


def placement(*, requested_cluster: str = "generic") -> SitePlacement:
    return SitePlacement(network="net-a", site="dc1", environment="PROD", cluster=requested_cluster)


class LastCandidateChooser(ClusterChooser):
    def choose(self, *, placement: SitePlacement, candidates: list[ConfiguredCluster]) -> ConfiguredCluster:
        return candidates[-1]


def resolver(*, clusters: list[ConfiguredCluster]) -> SiteClusterResolver:
    return SiteClusterResolver(
        directory=ClusterDirectory(clusters=clusters), chooser=SingleCandidateChooser()
    )


def test_a_generic_cluster_does_not_answer_a_request_for_its_name() -> None:
    with pytest.raises(expected_exception=NoMatchingClusterError):
        resolver(clusters=[cluster(name="orders")]).resolve(placement=placement(requested_cluster="orders"))


def test_a_named_cluster_must_be_dedicated_and_match_its_name_environment_and_site() -> None:
    wanted: ConfiguredCluster = cluster(name="orders", cluster_type="dedicated")
    clusters: list[ConfiguredCluster] = [
        cluster(name="orders", cluster_type="dedicated", environment="DEV"),
        cluster(name="orders", cluster_type="dedicated", site="dc2"),
        cluster(name="c1"),
        wanted,
    ]

    assert resolver(clusters=clusters).resolve(placement=placement(requested_cluster="orders")) == wanted


def test_a_generic_placement_takes_the_only_generic_cluster_at_the_site() -> None:
    generic: ConfiguredCluster = cluster(name="c1")
    clusters: list[ConfiguredCluster] = [cluster(name="orders", cluster_type="dedicated"), generic]

    assert resolver(clusters=clusters).resolve(placement=placement()) == generic


def test_a_generic_placement_leaves_the_choice_among_its_candidates_to_the_chooser() -> None:
    last: ConfiguredCluster = cluster(name="c2")
    directory: ClusterDirectory = ClusterDirectory(clusters=[cluster(name="c1"), last])

    chosen: ConfiguredCluster = SiteClusterResolver(
        directory=directory, chooser=LastCandidateChooser()
    ).resolve(placement=placement())

    assert chosen == last


@pytest.mark.parametrize(
    argnames="requested_placement",
    argvalues=[
        pytest.param(placement(), id="generic"),
        pytest.param(placement(requested_cluster="orders"), id="dedicated"),
    ],
)
def test_a_placement_without_a_configured_cluster_is_refused(requested_placement: SitePlacement) -> None:
    with pytest.raises(expected_exception=NoMatchingClusterError):
        resolver(clusters=[cluster(name="c1", site="dc2")]).resolve(placement=requested_placement)


def test_several_generic_clusters_at_a_site_cannot_be_chosen_yet() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        resolver(clusters=[cluster(name="c1"), cluster(name="c2")]).resolve(placement=placement())


def test_the_single_candidate_chooser_refuses_an_empty_candidate_list() -> None:
    with pytest.raises(expected_exception=NoMatchingClusterError):
        SingleCandidateChooser().choose(placement=placement(), candidates=[])
