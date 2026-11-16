from fastapi.openapi.models import Example

CREATE_CRDB_REQUEST_EXAMPLES: dict[str, Example] = {
    "two_sites": {
        "summary": "Two sites on one network, with the settings of the CRDB itself and one user",
        "description": "The first site coordinates the creation. Every spec.crdb field, and every "
        "database field, that is left out takes the service default for the target; when a default "
        "differs between the sites, the request is answered configuration_error naming those fields, and "
        "sending them explicitly avoids it. All sites must be on one network (else mixed_networks), and "
        "two sites may not resolve to the same cluster (else duplicate_sites).",
        "value": {
            "target": {
                "sites": [
                    {"environment": "PROD", "network": "net-a", "site": "NY", "cluster": "generic"},
                    {"environment": "PROD", "network": "net-a", "site": "TLV", "cluster": "generic"},
                ],
            },
            "spec": {
                "crdb": {"causal_consistency": False, "encryption": True, "compression": 3},
                "database": {"name": "orders", "memory_size": 1073741824},
                "users": [{"name": "app", "password": "S3cure-Passw0rd", "acl_rule": "+@all ~orders:*"}],
            },
        },
    },
    "minimal": {
        "summary": "Only the required fields: one site, one user, no spec.crdb",
        "description": "One site gives a CRDB with a single instance. The settings of the CRDB and every "
        "database setting that is not sent come from the service defaults for the target.",
        "value": {
            "target": {
                "sites": [{"environment": "PROD", "network": "net-a", "site": "NY", "cluster": "generic"}],
            },
            "spec": {
                "database": {"name": "orders", "memory_size": 1073741824},
                "users": [{"name": "app", "password": "S3cure-Passw0rd", "acl_rule": "+@all ~orders:*"}],
            },
        },
    },
}
