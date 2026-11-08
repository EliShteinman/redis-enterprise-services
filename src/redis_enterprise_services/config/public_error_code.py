from typing import Literal

type PublicErrorCode = Literal[
    "name_taken",
    "resources_locked",
    "invalid_name",
    "unknown_cluster",
    "cluster_unavailable",
    "cluster_request_failed",
    "cluster_timeout",
    "internal_error",
]
