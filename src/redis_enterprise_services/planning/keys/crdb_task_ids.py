from uuid import NAMESPACE_URL, uuid5

TASK_ID_NAMESPACE: str = "redis-enterprise-services/crdb-task"


def crdb_task_id(*, saga_id: str, step_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{TASK_ID_NAMESPACE}/{saga_id}/{step_key}"))
