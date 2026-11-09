import pytest
from pydantic import ValidationError

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
from redis_enterprise_services.planning.site_placement import ClusterChoice, SitePlacement


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


def placement(*, cluster_type: ClusterType = "generic", name: str | None = None) -> SitePlacement:
    return SitePlacement(
        network="net-a", site="dc1", environment="PROD", cluster=ClusterChoice(type=cluster_type, name=name)
    )


class LastCandidateChooser(ClusterChooser):
    def choose(self, *, placement: SitePlacement, candidates: list[ConfiguredCluster]) -> ConfiguredCluster:
        return candidates[-1]


def resolver(*, clusters: list[ConfiguredCluster]) -> SiteClusterResolver:
    return SiteClusterResolver(
        directory=ClusterDirectory(clusters=clusters), chooser=SingleCandidateChooser()
    )


def test_a_generic_cluster_does_not_answer_a_dedicated_placement_with_its_name() -> None:
    with pytest.raises(expected_exception=NoMatchingClusterError):
        resolver(clusters=[cluster(name="orders")]).resolve(
            placement=placement(cluster_type="dedicated", name="orders")
        )


def test_a_dedicated_cluster_must_match_name_type_environment_and_site() -> None:
    wanted: ConfiguredCluster = cluster(name="orders", cluster_type="dedicated")
    clusters: list[ConfiguredCluster] = [
        cluster(name="orders", cluster_type="dedicated", environment="DEV"),
        cluster(name="orders", cluster_type="dedicated", site="dc2"),
        cluster(name="c1"),
        wanted,
    ]

    assert (
        resolver(clusters=clusters).resolve(placement=placement(cluster_type="dedicated", name="orders"))
        == wanted
    )


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
        pytest.param(placement(cluster_type="dedicated", name="orders"), id="dedicated"),
    ],
)
def test_a_placement_without_a_configured_cluster_is_refused(requested_placement: SitePlacement) -> None:
    with pytest.raises(expected_exception=NoMatchingClusterError):
        resolver(clusters=[cluster(name="c1", site="dc2")]).resolve(placement=requested_placement)


def test_several_generic_clusters_at_a_site_cannot_be_chosen_yet() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        resolver(clusters=[cluster(name="c1"), cluster(name="c2")]).resolve(placement=placement())


@pytest.mark.parametrize(
    argnames=("cluster_type", "name"), argvalues=[("dedicated", None), ("generic", "c1")]
)
def test_only_a_dedicated_cluster_is_named(cluster_type: ClusterType, name: str | None) -> None:
    with pytest.raises(expected_exception=ValidationError):
        ClusterChoice(type=cluster_type, name=name)
