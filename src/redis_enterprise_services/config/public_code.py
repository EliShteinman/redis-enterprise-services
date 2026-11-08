from typing import Literal

type PublicCode = Literal[
    "name_taken",
    "database_locked",
    "invalid_name",
    "unknown_cluster",
    "cluster_unavailable",
    "step_rejected",
    "cluster_timeout",
    "internal_error",
]
