# redis-enterprise-services

Creates Redis Enterprise databases with their users, as a saga: each operation fully succeeds, rolls back, or stops
for manual intervention. Today: single-site and Active-Active creation. Planned: edit, delete. What exists and what is
missing: `docs/overview.md`.

## Requirements

- Python 3.14 and [uv](https://docs.astral.sh/uv/).
- A Redis for the saga state, on one shard without sharding, with a user that has `+@all -@dangerous +info ~res:*`
  (`res:` is the key prefix, `RES_STATE__KEY_PREFIX`).
- The proxy that routes every cluster call by the `x-network` header to cluster-relay; its address is `edge.url` in
  `helm/files/service.yaml`.
- Redis Enterprise clusters listed in `helm/files/clusters.yaml`, as a tree of environment (`dev`, `prod`, `test`),
  network, site and cluster. A cluster is named by its FQDN. Each level may set the cluster admin user, the password of
  the database default user and overrides of the database defaults of `helm/files/defaults.yaml`.

## Installation

```bash
uv sync
uv run pre-commit install
```

`uv.lock` is not kept in git. `uv sync` creates it on the first run; the pre-commit hooks need it.

## Running

Locally, from the project root, with the virtual environment that `uv sync` created:

```bash
python run_local.py
curl localhost:8080/health
```

It passes `helm/files/` and reads the two variables from `.env`. Copy `helm/files/clusters.example.yaml` to
`helm/files/clusters.yaml` and fill it in, and replace `fill-in-proxy-host` in `helm/files/service.yaml` with your proxy;
do not commit either.

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

## Configuration

Settings are in four files in `helm/files/`. The service reads them from the directory its caller passes; there is no
default. `run_local.py` passes `helm/files`.

| File | What | Changed when |
|---|---|---|
| `helm/files/clusters.yaml` | the clusters, as a tree of environment, network, site and cluster, with their admin users and the settings of each level | a cluster, site or network is added, or a value differs for one place |
| `helm/files/defaults.yaml` | what a database and its users get when nothing overrides it, and the naming rules | the defaults change |
| `helm/files/service.yaml` | how the service runs: server, API, logs, telemetry, relay, saga state, errors | the service is tuned |
| `helm/files/redis_api.yaml` | how the Redis Enterprise REST API is called: paths, fields, waits | Redis changes its API |

Each top-level key in a file is one settings topic. Any value can also be overridden by an environment variable with
the `RES_` prefix and `__` between levels, for example:

```bash
RES_LOG__LEVEL=DEBUG
```

The service needs exactly two environment variables, the access to the Redis that keeps the saga state:

- `RES_STATE__URL`: its connection string, with its user and password (`redis://user:password@host:port` or
  `rediss://...`).
- `RES_STATE__KEY_PREFIX`: the prefix of every key the service writes there (for example `res:`), the one its Redis
  user is allowed to use.

Locally they can be kept in a `.env` file instead. It is read from the working directory, so run the service from the
project root: copy `.env.example` to `.env` there and fill it in. `.env` is never committed, holds only `RES_`
variables, and an environment variable with the same name wins over it.

Every other secret is in `helm/files/clusters.yaml`:

```yaml
clusters:
  prod:                                   # environment: dev, prod or test
    username: admin@example.com           # cluster admin user
    api_port: 9443
    default_user_password: <password>     # of the default user of every new database
    database:
      version: "8.4"
    networks:
      net-a:
        password: <password>              # the admin password of the clusters of this network
        sites:
          NY:
            clusters:
              cluster-a.net-a.example.com:
                type: generic
              orders.net-a.example.com:
                type: dedicated
                password: <password>      # this cluster has its own admin password
                database:
                  replication: false
```

- The key of a cluster is its FQDN. The service calls it at `https://<FQDN>:<api_port>`. A port written in the key
  (`cluster-a.net-a.example.com:9444`) is used instead of `api_port`.
- `username`, `password`, `default_user_password`, `api_port` and `database` may be set on the environment, the network,
  the site and the cluster. The lowest level that sets a value wins.
- Every cluster must end up with `username`, `password`, `default_user_password` and a port. A cluster without one of
  them, the same FQDN twice, or a value that cannot apply, stops the service at start with an error that names it.
- Every call to a cluster uses the admin user of that cluster.
- `type: generic` clusters are picked by the service when a request asks for `generic`. A `dedicated` cluster is used
  only when a request names its FQDN.

Git holds only `helm/files/clusters.example.yaml`, an example with placeholders. Copy it to `helm/files/clusters.yaml`
(or to a file per environment, such as `prep-clusters.yaml`) and fill it in; files ending in `clusters.yaml` in
`helm/files/` are ignored by git.

Traces and metrics are sent over OTLP when `telemetry.export_enabled` is true, to `telemetry.otlp_endpoint`.

Logs go to the console, as lines or JSON (`log.console_format`). With `log.file.enabled` they also go to a rotating
file (`log.file`, JSON by default). Requests to `api.liveness_path` (`/health`) are left out of the logs below
`log.quiet_kept_level` (WARNING), and out of the traces and metrics.

## Tests, lint and type check

```bash
uv run pytest
```

`tests/integration/` runs the Redis scripts against the saga-state Redis given by the `RES_STATE__*` settings. Without
that Redis or those settings, the tests are skipped.

```bash
uv run ruff check . && uv run ruff format .
uv run basedpyright
uv run lint-imports
```

`lint-imports` checks the import direction between layers; the contracts are in `pyproject.toml`. The lint commands
run in pre-commit; the tests do not.
