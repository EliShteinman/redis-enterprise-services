import pytest
from pydantic import ValidationError

from redis_enterprise_services.config.clusters_settings import ClusterEntry, ClusterType, Environment
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.exceptions.planning import UnknownClusterError
from redis_enterprise_services.planning.cluster_chooser import ClusterChooser
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.cluster_resolver import ClusterResolver
from redis_enterprise_services.planning.single_candidate_chooser import SingleCandidateChooser
from redis_enterprise_services.planning.site_target import ClusterChoice, SiteTarget


def cluster(
    *, name: str, cluster_type: ClusterType = "generic", environment: Environment = "PROD", site: str = "dc1"
) -> ClusterEntry:
    return ClusterEntry(
        name=name,
        network="net-a",
        environment=environment,
        site=site,
        type=cluster_type,
        api_url=f"https://{name}:9443",
    )


def target(*, cluster_type: ClusterType = "generic", name: str | None = None) -> SiteTarget:
    return SiteTarget(
        network="net-a", site="dc1", environment="PROD", cluster=ClusterChoice(type=cluster_type, name=name)
    )


class LastCandidateChooser(ClusterChooser):
    def choose(self, *, target: SiteTarget, candidates: list[ClusterEntry]) -> ClusterEntry:
        return candidates[-1]


def resolver(*, clusters: list[ClusterEntry]) -> ClusterResolver:
    return ClusterResolver(directory=ClusterDirectory(clusters=clusters), chooser=SingleCandidateChooser())


def test_a_dedicated_cluster_is_found_by_all_four_parts() -> None:
    wanted: ClusterEntry = cluster(name="orders", cluster_type="dedicated")
    clusters: list[ClusterEntry] = [
        cluster(name="orders", cluster_type="dedicated", environment="DEV"),
        cluster(name="orders", cluster_type="dedicated", site="dc2"),
        cluster(name="c1"),
        wanted,
    ]

    assert (
        resolver(clusters=clusters).resolve(target=target(cluster_type="dedicated", name="orders")) == wanted
    )


def test_a_generic_target_takes_the_only_generic_cluster_at_the_site() -> None:
    generic: ClusterEntry = cluster(name="c1")
    clusters: list[ClusterEntry] = [cluster(name="orders", cluster_type="dedicated"), generic]

    assert resolver(clusters=clusters).resolve(target=target()) == generic


def test_a_generic_target_leaves_the_choice_among_its_candidates_to_the_chooser() -> None:
    last: ClusterEntry = cluster(name="c2")
    directory: ClusterDirectory = ClusterDirectory(clusters=[cluster(name="c1"), last])

    chosen: ClusterEntry = ClusterResolver(directory=directory, chooser=LastCandidateChooser()).resolve(
        target=target()
    )

    assert chosen == last


@pytest.mark.parametrize(
    argnames="wanted",
    argvalues=[
        pytest.param(target(), id="generic"),
        pytest.param(target(cluster_type="dedicated", name="orders"), id="dedicated"),
    ],
)
def test_a_target_without_a_configured_cluster_is_unknown(wanted: SiteTarget) -> None:
    with pytest.raises(expected_exception=UnknownClusterError):
        resolver(clusters=[cluster(name="c1", site="dc2")]).resolve(target=wanted)


def test_several_generic_clusters_at_a_site_cannot_be_chosen_yet() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        resolver(clusters=[cluster(name="c1"), cluster(name="c2")]).resolve(target=target())


@pytest.mark.parametrize(
    argnames=("cluster_type", "name"), argvalues=[("dedicated", None), ("generic", "c1")]
)
def test_only_a_dedicated_cluster_is_named(cluster_type: ClusterType, name: str | None) -> None:
    with pytest.raises(expected_exception=ValidationError):
        ClusterChoice(type=cluster_type, name=name)
