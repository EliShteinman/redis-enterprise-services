from pydantic import BaseModel


class ClusterFieldSettings(BaseModel):
    status: str
    error_code: str


class FieldsQuerySettings(BaseModel):
    name: str
    separator: str


class ClusterSettings(BaseModel):
    fields: ClusterFieldSettings
    fields_query: FieldsQuerySettings
