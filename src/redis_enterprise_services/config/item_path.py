from string import Formatter
from typing import Annotated

from pydantic import AfterValidator

ITEM_PLACEHOLDERS: frozenset[str] = frozenset({"uid"})


def reject_item_path_without_only_the_uid_placeholder(path: str) -> str:
    placeholders: frozenset[str] = frozenset(
        field for _, field, _, _ in Formatter().parse(path) if field is not None
    )
    if placeholders != ITEM_PLACEHOLDERS:
        raise ValueError(f"{path} must use exactly the placeholders {sorted(ITEM_PLACEHOLDERS)}")
    return path


type ItemPath = Annotated[str, AfterValidator(reject_item_path_without_only_the_uid_placeholder)]
