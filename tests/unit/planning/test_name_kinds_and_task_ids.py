from typing import get_args

from redis_enterprise_services.planning.crdb_task_ids import crdb_task_id
from redis_enterprise_services.planning.name_kind import NAME_KINDS, NameKind


def test_the_name_kinds_constant_lists_every_name_kind() -> None:
    assert set(get_args(NameKind.__value__)) == NAME_KINDS


def test_a_crdb_task_id_never_changes_for_the_same_saga_and_step() -> None:
    assert crdb_task_id(saga_id="trace-1", step_key="crdb") == "ca5bf89a-e84e-5e95-bf3d-9396395ea32b"
