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

## Configuration

Copy `.env.example` to `.env` and fill it in. Docket reads standard AWS
credentials (`AWS_PROFILE`, `AWS_DEFAULT_REGION`, etc.) plus its own
`DOCKET_*` variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCKET_AWS_REGIONS` | all regions | Comma-separated regions Steampipe scans. NOTE: Leaving this empty means Steampipe scans ALL regions |
| `DOCKET_DB_PATH` | `docket.db` | Path to the sqlite catalog file |
| `DOCKET_LLM_MODEL` | — | [litellm](https://docs.litellm.ai/) model string, e.g. `anthropic/claude-sonnet-5`; required by `docket run` |
| `DOCKET_LLM_API_KEY` | — | LLM provider key; omit for providers authenticated elsewhere (e.g. Bedrock via AWS credentials) |
| `DOCKET_LLM_WORKSPACE_ID` | — | Workspace ID, required only by identity-linked keys |
| `DOCKET_LLM_CONCURRENCY` | `8` | Parallel extraction calls |
| `DOCKET_LOG_LEVEL` | — | Log level for the docket namespace |
| `DOCKET_SERVE_HOST` | `127.0.0.1` | Web UI bind host |
| `DOCKET_SERVE_PORT` | `8000` | Web UI bind port |

`.env` files are loaded at the app edge

```bash
uv run --env-file .env docket <command>
```

## Usage

### `docket run`

Rebuilds the catalog from AWS and extracts lineage edges. Reads the Glue and
Lambda inventory, downloads job sources, then truncates and repopulates the
catalog in one transaction. Extractions are cached by source content, so only
jobs whose code changed hit the LLM on subsequent runs.

### `docket check-delete DATABASE TABLE`

Reports every job and table that would break if the table were deleted:
direct readers, tables written by those readers, join references, and the
transitive blast radius. Exits 1 when the table has dependents, so it works
as a guard in scripts and CI.

### `docket audit [--hours N] [--all]`

Queries CloudTrail for recent `DeleteTable` / `BatchDeleteTable` events and
flags any deleted table that still had dependents in the catalog. `--all` re-reports everything in the window. Exits 1 when a flagged deletion is found.

### `docket serve`

Serves the catalog browser at `http://127.0.0.1:8000`: table search, column search, per-table detail pages with dependents, and an interactive lineage DAG.

## Repository Layout

Everything persists in one sqlite file. The Steampipe AWS extension is loaded
onto the same connection, so AWS appears as virtual tables (`aws_*`) queried
live alongside the persisted catalog tables (`catalog_*`). Each table gets a
folder under `src/docket/db/` with its model and client; `db/db.py` exports
the single `DB` entry point that owns the connection, migrations, and
transactions. The orchestrator (`src/docket/orchestrator/`) rebuilds the
catalog and runs the LLM edge extraction; the web app (`src/docket/web/`) and
CLI (`src/docket/cli.py`) read from the result.

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
