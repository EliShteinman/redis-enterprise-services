# redis-enterprise-services

Creates, edits and deletes Redis Enterprise databases. Each operation fully succeeds or rolls back.

## Installation

```bash
uv sync
uv run pre-commit install
```

## Running

Locally, from the project root (host and port come from `config/server.yaml`):

```bash
uv run python run.py
curl localhost:8080/health
```

In a deployment, uvicorn builds the app through the factory:

```bash
uv run uvicorn redis_enterprise_services.app:create_app --factory --host 0.0.0.0 --port 8080
```

## Configuration

Settings are in `config/`, one YAML file per topic (`log.yaml`, `api.yaml`, `telemetry.yaml`, `edge.yaml`,
`action.yaml`, `acl.yaml`, `cluster.yaml`, `database.yaml`, `role.yaml`, `saga.yaml`, `state.yaml`,
`user.yaml`), read from the working directory. Any value can be overridden by an environment variable with the
`RES_` prefix and `__` between levels, for example:

```bash
RES_LOG__LEVEL=DEBUG
```

Secrets are passed only through environment variables. Required:

- `RES_STATE__PASSWORD`: the password of the Redis that keeps the saga state.
- `RES_DATABASE__DEFAULT_USER_PASSWORD`: the `default_user` password every new database is created with.

Traces and metrics are sent over OTLP when `telemetry.export_enabled` is true, to `telemetry.otlp_endpoint`.

## Lint

```bash
uv run ruff check . && uv run ruff format .
uv run basedpyright
uv run lint-imports
```

`lint-imports` checks the import direction between layers; the contracts are in `pyproject.toml`. All of these run in pre-commit.

## Local clusters

`docker/compose.yaml` runs two Redis Enterprise clusters. Copy `docker/.env.example` to `docker/.env` and fill in
the passwords. Put the Redis Software license in `docker/license/license.txt` (never committed), then:

```bash
docker compose -f docker/compose.yaml up -d
```
