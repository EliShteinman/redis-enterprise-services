# redis-enterprise-services

Creates, edits and deletes Redis Enterprise databases. Each operation fully succeeds or rolls back.

## Installation

```bash
uv sync
uv run pre-commit install
```

## Running

From the project root:

```bash
uv run uvicorn redis_enterprise_services.app:create_app --factory --host 0.0.0.0 --port 8000
curl localhost:8000/health
```

## Configuration

All settings are in `config/settings.yaml`, read from the working directory. Any value can be overridden by an
environment variable with the `RES_` prefix and `__` between levels, for example:

```bash
RES_LOG__LEVEL=DEBUG
```

Secrets are passed only through environment variables.

## Lint

```bash
uv run ruff check . && uv run ruff format .
```

## Local clusters

`docker/compose.yaml` runs two Redis Enterprise clusters. Copy `docker/.env.example` to `docker/.env` and fill in
the passwords. Put the Redis Software license in `docker/license/license.txt` (never committed), then:

```bash
docker compose -f docker/compose.yaml up -d
```
