from redis_enterprise_services.crdbs.models import Crdb


def test_the_local_instance_is_found_by_the_cluster_api_url() -> None:
    crdb: Crdb = Crdb.model_validate(
        obj={
            "guid": "g",
            "name": "orders",
            "default_db_config": {},
            "instances": [
                {"id": 1, "cluster": {"url": "https://cluster-a.net-a:9443"}, "db_uid": "7"},
                {"id": 2, "cluster": {"url": "https://cluster-b.net-a:9443"}},
            ],
        }
    )

    assert crdb.instance_on(api_url="https://cluster-a.net-a:9443") == crdb.instances[0]
