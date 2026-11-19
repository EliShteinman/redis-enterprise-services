from redis_enterprise_services.cluster.error_cluster_url import with_cluster_url
from redis_enterprise_services.exceptions.cluster import CrdbTaskFailedError


def test_an_error_that_already_names_its_cluster_keeps_it() -> None:
    error: CrdbTaskFailedError = CrdbTaskFailedError(message="failed", cluster_error_code=None)
    error.cluster_url = "https://c2:9443"

    assert with_cluster_url(error=error, cluster_url="https://c1:9443").cluster_url == "https://c2:9443"
