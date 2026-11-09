from typing import Annotated

from pydantic import AfterValidator

from redis_enterprise_services.config.template_placeholders import template_placeholders

ITEM_PLACEHOLDERS: frozenset[str] = frozenset({"uid"})


def reject_item_path_not_exactly_uid_placeholder(path: str) -> str:
    placeholders: frozenset[str] = template_placeholders(template=path)
    if placeholders != ITEM_PLACEHOLDERS:
        raise ValueError(f"{path} must use exactly the placeholders {sorted(ITEM_PLACEHOLDERS)}")
    return path


type ItemPath = Annotated[str, AfterValidator(reject_item_path_not_exactly_uid_placeholder)]
