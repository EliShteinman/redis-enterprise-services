from fastapi.openapi.models import Example

CREATION_EXAMPLES: dict[str, Example] = {
    "minimal": {
        "summary": "A database with one user, on a cluster the service picks",
        "description": "Only the required fields. Every other database setting comes from the service "
        "defaults for the target environment.",
        "value": {
            "target": {
                "active_active": False,
                "sites": [
                    {"network": "net-a", "site": "dc1", "environment": "PROD", "cluster": {"type": "generic"}}
                ],
            },
            "body": {
                "database": {"name": "orders", "memory_size": 1073741824},
                "users": [{"name": "app", "password": "S3cure-Passw0rd", "acl": "+@all ~orders:*"}],
            },
        },
    },
    "dedicated": {
        "summary": "A sharded database with snapshots and two users, on a named cluster",
        "description": "A dedicated cluster is named in cluster.name. "
        "The settings that are sent override the defaults.",
        "value": {
            "target": {
                "active_active": False,
                "sites": [
                    {
                        "network": "net-a",
                        "site": "dc1",
                        "environment": "PROD",
                        "cluster": {"type": "dedicated", "name": "cluster-a"},
                    }
                ],
            },
            "body": {
                "database": {
                    "name": "sessions",
                    "memory_size": 4294967296,
                    "replication": True,
                    "sharding": True,
                    "shards_count": 2,
                    "shard_key_regex": [{"regex": ".*\\{(?<tag>.*)\\}.*"}, {"regex": "(?<tag>.*)"}],
                    "data_persistence": "snapshot",
                    "snapshot_policy": [{"secs": 3600, "writes": 1}],
                    "eviction_policy": "allkeys-lru",
                },
                "users": [
                    {"name": "web", "password": "S3cure-Passw0rd", "acl": "+@all ~session:*"},
                    {"name": "reporter", "password": "An0ther-Passw0rd", "acl": "+@read ~session:*"},
                ],
            },
        },
    },
}
