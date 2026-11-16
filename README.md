# redis-enterprise-services

Creates Redis Enterprise databases with their users, as a saga: each operation fully succeeds, rolls back, or stops
for manual intervention. Today: single-site creation. Planned: Active-Active, edit, delete. What exists and what is
missing: `docs/overview.md`.

## Requirements

- Python 3.14 and [uv](https://docs.astral.sh/uv/).
- A Redis for the saga state, on one shard without sharding, with a user that has `+@all -@dangerous +info ~res:*`
  (`res:` is `state.key_prefix` in `config/state.yaml`).
- The proxy that routes every cluster call by the `x-network` header to cluster-relay; its address is `edge.url` in
  `config/edge.yaml`.
- Redis Enterprise clusters listed in `config/clusters.yaml`.

## Installation

```bash
uv sync
uv run pre-commit install
```

`uv.lock` is not kept in git. `uv sync` creates it on the first run; the pre-commit hooks need it.

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

Every command needs its own trace id: the same trace id again returns the existing operation (`200`) instead of
starting a new one. The OpenAPI docs, with request examples, are at `/docs`.

In a deployment, uvicorn builds the app through the factory:

```bash
uv run uvicorn redis_enterprise_services.app:create_app --factory --host 0.0.0.0 --port 8080
```

## Configuration

Settings are in `config/`, one YAML file per topic, read from the working directory. Any value can be overridden by
an environment variable with the `RES_` prefix and `__` between levels, for example:

```bash
RES_LOG__LEVEL=DEBUG
```

Secrets are passed only through environment variables. Required:

- `RES_STATE__URL`: the connection string of the Redis that keeps the saga state, with its user and password
  (`redis://user:password@host:port` or `rediss://...`).
- `RES_DATABASE__DEFAULT_USER_PASSWORD`: the `default_user` password every new database is created with.
- `RES_CLUSTER_CREDENTIALS__USERNAME`, `RES_CLUSTER_CREDENTIALS__PASSWORD`: the admin user of the clusters.

Locally they can be kept in a `.env` file instead. Like the YAML files, it is read from the working directory, so run
the service from the project root: copy `.env.example` to `.env` there and fill it in. `.env` is never committed,
holds only `RES_` variables, and an environment variable with the same name wins over it.

Traces and metrics are sent over OTLP when `telemetry.export_enabled` is true, to `telemetry.otlp_endpoint`.

## Tests, lint and type check

```bash
uv run pytest
```

`tests/integration/` runs the Redis scripts against the saga-state Redis given by the `RES_STATE__*` settings. Without
that Redis or those settings, the tests are skipped.

```bash
uv run ruff check . && uv run ruff format .
uv run basedpyright
```

The lint commands run in pre-commit; the tests do not.
