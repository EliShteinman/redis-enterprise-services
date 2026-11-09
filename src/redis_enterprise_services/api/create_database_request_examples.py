from fastapi.openapi.models import Example

CREATE_DATABASE_REQUEST_EXAMPLES: dict[str, Example] = {
    "full": {
        "summary": "Every field: a sharded database with two users, on a named cluster",
        "description": "Every field the request accepts. Only target, spec.database.name and "
        "spec.database.memory_size are required; any other database field that is left out "
        "takes the service default for the target. "
        "aof_policy applies only with aof, and snapshot_policy only with snapshot.",
        "value": {
            "target": {
                "active_active": False,
                "sites": [
                    {
                        "network": "net-a",
                        "site": "dc1",
                        "environment": "PROD",
                        "cluster": "cluster-a",
                    }
                ],
            },
            "spec": {
                "database": {
                    "name": "orders",
                    "memory_size": 1073741824,
                    "version": "8.4",
                    "replication": True,
                    "sharding": True,
                    "shards_count": 2,
                    "shard_key_regex": [{"regex": ".*\\{(?<tag>.*)\\}.*"}, {"regex": "(?<tag>.*)"}],
                    "data_persistence": "aof",
                    "aof_policy": "appendfsync-every-sec",
                    "snapshot_policy": [{"secs": 3600, "writes": 1}],
                    "eviction_policy": "volatile-lru",
                    "shards_placement": "dense",
                    "proxy_policy": "all-master-shards",
                    "slave_ha": True,
                },
                "users": [
                    {"name": "app", "password": "S3cure-Passw0rd", "acl_rule": "+@all ~orders:*"},
                    {"name": "reporter", "password": "An0ther-Passw0rd", "acl_rule": "+@read ~orders:*"},
                ],
            },
        },
    },
    "minimal": {
        "summary": "Only the required fields: one user, on a cluster the service picks",
        "description": "Every database setting that is not sent comes from the service defaults "
        "for the target.",
        "value": {
            "target": {
                "active_active": False,
                "sites": [{"network": "net-a", "site": "dc1", "environment": "PROD", "cluster": "generic"}],
            },
            "spec": {
                "database": {"name": "orders", "memory_size": 1073741824},
                "users": [{"name": "app", "password": "S3cure-Passw0rd", "acl_rule": "+@all ~orders:*"}],
            },
        },
    },
}
