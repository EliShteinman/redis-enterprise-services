from typing import Literal

type PublicErrorCode = Literal[
    "name_taken",
    "resources_locked",
    "invalid_name",
    "no_matching_cluster",
    "cluster_unavailable",
    "cluster_request_failed",
    "cluster_timeout",
    "configuration_error",
    "internal_error",
]
