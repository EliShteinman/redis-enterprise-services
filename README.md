# redis-enterprise-services

Creates Redis Enterprise databases with their users, as a saga: each operation fully succeeds, rolls back, or stops
for manual intervention. Today: single-site creation. Planned: Active-Active, edit, delete. What exists and what is
missing: `docs/overview.md`.

## Requirements

- Python 3.14 and [uv](https://docs.astral.sh/uv/).
- A Redis for the saga state, reachable at `state.host:state.port` (`config/state.yaml`), with a user that has
  `+@all -@dangerous +info ~res:*` (`res:` is `state.key_prefix`).
- cluster-relay running for each network in `config/edge.yaml` (locally: `http://127.0.0.1:8000/`).
- Redis Enterprise clusters listed in `config/clusters.yaml`.

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

- `RES_STATE__PASSWORD`: the password of the Redis that keeps the saga state.
- `RES_DATABASE__DEFAULT_USER_PASSWORD`: the `default_user` password every new database is created with.
- `RES_CLUSTER_CREDENTIALS__USERNAME`, `RES_CLUSTER_CREDENTIALS__PASSWORD`: the admin user of the clusters.
- `RES_EDGE__NETWORKS__<network>__FIREWALL__PASSWORD`: only for a network whose `firewall` is set in `config/edge.yaml`.

Locally they can be kept in a `.env` file instead. Like the YAML files, it is read from the working directory, so run
the service from the project root: copy `.env.example` to `.env` there and fill it in. `.env` is never committed,
holds only `RES_` variables, and an environment variable with the same name wins over it.

Traces and metrics are sent over OTLP when `telemetry.export_enabled` is true, to `telemetry.otlp_endpoint`.

## Tests, lint and type check

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run ruff format .
uv run basedpyright
uv run lint-imports
```

`lint-imports` checks the import direction between layers; the contracts are in `pyproject.toml`. The lint commands
run in pre-commit; the tests do not.

## Local clusters

`docker/compose.yaml` runs two Redis Enterprise clusters, for local development only. Copy `docker/.env.example` to
`docker/.env` and fill in the passwords. Put the Redis Software license in `docker/license/license.txt` (never
committed). The bootstrap jobs send every cluster call through cluster-relay (`BOOTSTRAP_RELAY_URL`, by default
`http://host.docker.internal:8000/`), so start the relay first, then:

```bash
docker compose -f docker/compose.yaml up -d
```

The service logs in to these clusters with `RES_CLUSTER_CREDENTIALS__USERNAME` and `RES_CLUSTER_CREDENTIALS__PASSWORD`,
so set them to `CLUSTER_ADMIN_USERNAME` and `CLUSTER_ADMIN_PASSWORD` from `docker/.env`.

To use another subnet, change `NETWORK_SUBNET`, `NETWORK_DYNAMIC_IP_RANGE` and the three `*_IP` values together in
`docker/.env`.

The saga-state Redis is not created by the compose file. Create it once on cluster1 (its mapped ports are
12000-12010):

- a database listening on port `12005` (`state.port`);
- an ACL `+@all -@dangerous +info ~res:*` (`res:` is `state.key_prefix`), a role with that ACL on the database, and a
  user `saga-service` (`state.username`) with that role and the password in `RES_STATE__PASSWORD`.
