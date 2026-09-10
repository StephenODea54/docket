# docket

Docket catalogs your AWS data infrastructure into a local sqlite file and maps
the lineage between its tables and jobs. It inventories Glue databases, tables, jobs and
Lambda functions through [Steampipe](https://steampipe.io/), reads each job's
source code, and uses an LLM to extract which tables every job reads, writes,
and joins. The result is a dependency graph you can query before deleting a
table, browse in a web UI, or audit against CloudTrail to catch deletions that
broke something downstream. It also creates automatic ERD diagrams by checking the SQL join conditions in the Glue job and Lambda scripts.

## Installation

Docket is managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

The Steampipe AWS extension is downloaded and cached automatically on first
run (under `~/.docket/steampipe/`).

The `lambda` extra (`uv sync --extra lambda`) adds what `docket serve --adapter
lambda` needs; it only installs on Linux.

## Configuration

Copy `.env.example` to `.env` and fill it in. Docket reads standard AWS
credentials (`AWS_PROFILE`, `AWS_DEFAULT_REGION`, etc.) plus its own
`DOCKET_*` variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCKET_AWS_REGIONS` | all regions | Comma-separated regions Steampipe scans. NOTE: Leaving this empty means Steampipe scans ALL regions |
| `DOCKET_DB_PATH` | `docket.db` | Where the catalog lives: a local sqlite path or an `s3://bucket/key` uri. With s3, every command downloads a copy to `~/.docket/cache/` first (`/tmp` when home is read-only, e.g. Lambda); `docket run` uploads on success and `docket audit` uploads after recording new events |
| `DOCKET_IGNORE_JOBS` | CDK helpers | Regex of job and function names `docket run` catalogs but never sends to the extractor. Unset matches the helper functions the AWS CDK deploys alongside stacks (`LogRetention`, `BucketNotificationsHandler`, `CustomCDKBucketDeploymen`, ...); set it empty to disable ignoring |
| `DOCKET_LLM_MODEL` | — | [litellm](https://docs.litellm.ai/) model string, e.g. `anthropic/claude-sonnet-5`; required by `docket run` |
| `DOCKET_LLM_API_KEY` | — | LLM provider key; omit for providers authenticated elsewhere (e.g. Bedrock via AWS credentials) |
| `DOCKET_LLM_WORKSPACE_ID` | — | Workspace ID, required only by identity-linked keys |
| `DOCKET_LLM_CONCURRENCY` | `8` | Parallel extraction calls |
| `DOCKET_LOG_LEVEL` | — | Log level for the docket namespace |
| `DOCKET_SERVE_ADAPTER` | `uvicorn` | How `docket serve` hosts the app: `uvicorn` or `lambda` |
| `DOCKET_SERVE_HOST` | `127.0.0.1` | Web UI bind host (uvicorn adapter) |
| `DOCKET_SERVE_PORT` | `8000` | Web UI bind port (uvicorn adapter) |

`.env` files are loaded at the app edge

```bash
uv run --env-file .env docket <command>
```

## Usage

### `docket run`

Rebuilds the catalog from AWS and extracts lineage edges. Reads the Glue and
Lambda inventory, downloads job sources, then truncates and repopulates the
catalog in one transaction. Extractions are cached by source content, so only
jobs whose code changed hit the LLM on subsequent runs. Jobs matching
`DOCKET_IGNORE_JOBS` still appear in the catalog but are never extracted.

### `docket check-delete DATABASE TABLE`

Reports every job and table that would break if the table were deleted:
direct readers, tables written by those readers, join references, and the
transitive blast radius. Exits 1 when the table has dependents, so it works
as a guard in scripts and CI. The first line reports how long ago the catalog
was last written, read from wherever `DOCKET_DB_PATH` points.

### `docket audit [--hours N] [--all] [--report PATH]`

Queries CloudTrail for recent `DeleteTable` / `BatchDeleteTable` events and
flags any deleted table that still had dependents in the catalog. Findings are
grouped per table: one block listing every deletion (event name, principal,
count, time span, regions) followed by the table's dependents report. `--all`
re-reports everything in the window. `--report` also writes the full report to
a local path or an `s3://bucket/key` uri, including a "none had dependents"
report on clean runs. Exits 1 when a flagged deletion is found.

### `docket serve [--adapter uvicorn|lambda]`

Serves the catalog browser at `http://127.0.0.1:8000`: table search, column search, per-table detail pages with dependents, and an interactive lineage DAG.

The adapter picks how the app is hosted. `uvicorn` binds a socket on
`DOCKET_SERVE_HOST:DOCKET_SERVE_PORT`. `lambda` wraps the app with
[Mangum](https://mangum.fastapiexpert.com/) and runs the AWS Lambda Runtime
Interface Client, so the published container image can be deployed as a Lambda
function behind API Gateway, an ALB, or a Function URL with no extra layers or
wrapper scripts (`CMD ["serve", "--adapter", "lambda"]`). It needs the `lambda`
extra, which the published image includes. Adding a runtime means adding one
`ServeAdapterStrategy` subclass under `src/docket/web/adapters/`.

`serve` opens the catalog as plain sqlite without the Steampipe extension, so
it needs no AWS credentials beyond what an `s3://` `DOCKET_DB_PATH` requires.
With an `s3://` path it downloads the catalog once on startup; restart the
process to pick up a newer copy.

## Repository Layout

Everything persists in one sqlite file. The Steampipe AWS extension is loaded
onto the same connection, so AWS appears as virtual tables (`aws_*`) queried
live alongside the persisted catalog tables (`catalog_*`). Each table gets a
folder under `src/docket/db/` with its model and client; `db/db.py` exports
the single `DB` entry point that owns the connection, migrations, and
transactions. The orchestrator (`src/docket/orchestrator/`) rebuilds the
catalog and runs the LLM edge extraction; the web app (`src/docket/web/`) and
CLI (`src/docket/cli.py`) read from the result. `src/docket/store/` holds one
`CatalogStoreStrategy` per place the catalog can live (local disk, s3);
`catalog_store()` picks one from the `DOCKET_DB_PATH` value so the CLI never
branches on it. `src/docket/web/adapters/` holds one `ServeAdapterStrategy` per
way of hosting the web app.

The ORM and migrations come from [sustained](https://sustained.tbmh.org/).

## Development

```bash
uv sync
uv run pre-commit install
uv run pytest
```

Linting and formatting are handled by [Ruff](https://docs.astral.sh/ruff/)
via [pre-commit](https://pre-commit.com/); the hooks run automatically on
commit, or on demand with:

```bash
uv run pre-commit run --all-files
```
