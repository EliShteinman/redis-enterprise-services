from redis_enterprise_services.config.database_defaults_settings import DatabaseDefaultsSettings, DatabaseKind


def test_every_kind_of_database_names_a_set_of_defaults() -> None:
    assert set(DatabaseKind) == set(DatabaseDefaultsSettings.model_fields)
