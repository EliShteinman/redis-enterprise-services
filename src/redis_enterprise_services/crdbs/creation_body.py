from pydantic import BaseModel, Field, JsonValue

from redis_enterprise_services.cluster.api_host import api_host_of
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings


class CrdbClusterCredentials(BaseModel):
    username: str
    password: str = Field(repr=False)


class CrdbClusterInfo(BaseModel):
    url: str
    name: str
    credentials: CrdbClusterCredentials


class CrdbInstanceInfo(BaseModel):
    cluster: CrdbClusterInfo
    compression: int


class CrdbCreationBody(BaseModel):
    name: str
    default_db_config: dict[str, JsonValue] = Field(repr=False)
    causal_consistency: bool
    encryption: bool
    instances: list[CrdbInstanceInfo]


def crdb_creation_body(
    *,
    name: str,
    default_db_config: dict[str, JsonValue],
    members: list[ClusterTarget],
    settings: CrdbCreationSettings,
) -> CrdbCreationBody:
    return CrdbCreationBody(
        name=name,
        default_db_config=default_db_config,
        causal_consistency=settings.causal_consistency,
        encryption=settings.encryption,
        instances=[crdb_instance(target=member, compression=settings.compression) for member in members],
    )


def crdb_instance(*, target: ClusterTarget, compression: int) -> CrdbInstanceInfo:
    return CrdbInstanceInfo(
        compression=compression,
        cluster=CrdbClusterInfo(
            url=target.api_url,
            name=api_host_of(api_url=target.api_url),
            credentials=CrdbClusterCredentials(
                username=target.credentials.username, password=target.credentials.password.get_secret_value()
            ),
        ),
    )
