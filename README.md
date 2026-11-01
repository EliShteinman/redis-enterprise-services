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

Create a database (the request is in `docs/contracts/service-api.md`), then ask for its status by the returned
`trace_id`:

```bash
curl -X POST localhost:8080/v1/databases/create -H 'content-type: application/json' \
  -H 'traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01' -d @request.json
curl localhost:8080/v1/operations/4bf92f3577b34da6a3ce929d0e0e4736 \
  -H 'traceparent: 00-5c8a1e2f3b4d6e7f8091a2b3c4d5e6f7-1a2b3c4d5e6f7081-01'
```

In a deployment, uvicorn builds the app through the factory:

```bash
uv run uvicorn redis_enterprise_services.app:create_app --factory --host 0.0.0.0 --port 8080
```

## Configuration

Settings are in `config/`, one YAML file per topic, read from the working directory. Any value can be overridden by an environment variable with the
`RES_` prefix and `__` between levels, for example:

```bash
RES_LOG__LEVEL=DEBUG
```

Secrets are passed only through environment variables. Required:

- `RES_STATE__PASSWORD`: the password of the Redis that keeps the saga state.
- `RES_DATABASE__DEFAULT_USER_PASSWORD`: the `default_user` password every new database is created with.
- `RES_CLUSTER_ACCESS__USERNAME`, `RES_CLUSTER_ACCESS__PASSWORD`: the admin user of the clusters.

Locally they can be kept in a `.env` file instead. Like the YAML files, it is read from the working directory, so run
the service from the project root: copy `.env.example` to `.env` there and fill it in. `.env` is never committed, holds only `RES_` variables, and an environment variable with the same name wins over
it.

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
