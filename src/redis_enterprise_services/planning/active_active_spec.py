from pydantic import Field

from redis_enterprise_services.planning.crdb_spec import CrdbSpec
from redis_enterprise_services.planning.database_spec import DatabaseSpec


class ActiveActiveSpec(DatabaseSpec):
    crdb: CrdbSpec | None = Field(
        default=None,
        description="The settings of the Active-Active database itself. A field not sent, or the whole "
        "object not sent, takes the values configured for the environment and network.",
    )
