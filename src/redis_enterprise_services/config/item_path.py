from typing import Annotated

from pydantic import AfterValidator, Field

from redis_enterprise_services.config.template_placeholders import reject_placeholders_other_than

ITEM_PLACEHOLDERS: frozenset[str] = frozenset({"uid"})


def reject_item_path_not_exactly_uid_placeholder(path: str) -> str:
    reject_placeholders_other_than(template=path, allowed=ITEM_PLACEHOLDERS)
    return path


type ApiPath = Annotated[str, Field(pattern=r"^/")]
type ItemPath = Annotated[ApiPath, AfterValidator(reject_item_path_not_exactly_uid_placeholder)]
