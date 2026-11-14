from uuid import NAMESPACE_URL, uuid5

UNDO_TASK_ID_NAMESPACE: str = "redis-enterprise-services/crdb-undo-task"


def undo_task_id(*, task_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{UNDO_TASK_ID_NAMESPACE}/{task_id}"))
