import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import typer
import uvicorn

from .config.env import env
from .db import DB
from .lineage import DependentsReport, collect_dependents, format_report
from .orchestrator import LlmEdgeExtractor
from .orchestrator import run as run_pipeline
from .web import create_app

app = typer.Typer(no_args_is_help=True)


def _open_db(db_path: str | None) -> tuple[DB, str]:
    """
    Resolve the db path, require it to exist, and open + migrate.

    Args:
        db_path: path to the sqlite file, or None to use DOCKET_DB_PATH

    Returns:
        The open database and the resolved path

    Raises:
        typer.Exit: with code 2 when the resolved path does not exist
    """
    resolved = db_path or env.db_path
    if not Path(resolved).exists():
        typer.echo(f"{resolved} does not exist; run `docket run` first", err=True)
        raise typer.Exit(2)
    db = DB(resolved)
    db.migrate()
    return db, resolved


def _catalog_age(db_path: str) -> str:
    """
    Format how long ago the catalog file was last written.

    Args:
        db_path: path to the sqlite file

    Returns:
        The staleness line printed by the check and audit commands
    """
    modified = datetime.fromtimestamp(os.path.getmtime(db_path), tz=UTC)
    hours = (datetime.now(UTC) - modified).total_seconds() / 3600
    return f"catalog file last written ~{hours:.1f}h ago ({db_path} mtime)"


def _collect_dependents(db: DB, database: str, table: str) -> DependentsReport:
    """Run the dependents walk for a table against the catalog clients."""
    row = db.clients["catalog_tables"].get_table(database, table)
    return collect_dependents(
        database,
        table,
        db.clients["catalog_job_table_edges"].get_table_edges,
        db.clients["catalog_job_table_edges"].get_job_edges,
        db.clients["catalog_table_join_edges"].get_table_edges,
        db.clients["catalog_jobs"].get_jobs_by_ids,
        db.clients["catalog_tables"].get_tables_by_names,
        in_catalog=row is not None,
    )


@app.callback()
def main() -> None:
    """Catalog AWS data infrastructure and extract lineage edges."""
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def run() -> None:
    """Rebuild the catalog from AWS and extract edges for changed jobs."""
    try:
        extractor = LlmEdgeExtractor.from_env()
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(2) from error
    job_ids = run_pipeline(DB(), extractor)
    typer.echo(f"re-extracted {len(job_ids)} jobs")


@app.command(name="check-delete")
def check_delete(database: str, table: str, db_path: str | None = None) -> None:
    """Report every job and table that would break if the table were deleted."""
    db, resolved = _open_db(db_path)
    typer.echo(_catalog_age(resolved))
    report = _collect_dependents(db, database, table)
    if not report["in_catalog"]:
        typer.echo(
            f"warning: {database}.{table} is not in the catalog snapshot; "
            "checking edges anyway",
            err=True,
        )
    typer.echo(format_report(report))
    if report["has_dependents"]:
        raise typer.Exit(1)


@app.command()
def serve(
    host: str | None = None,
    port: int | None = None,
    db_path: str | None = None,
) -> None:
    """Serve the catalog browser web UI."""
    resolved_host = host or env.serve_host
    resolved_port = port or env.serve_port
    resolved_db_path = db_path or env.db_path
    if not Path(resolved_db_path).exists():
        typer.echo(
            f"{resolved_db_path} does not exist; run `docket run` first", err=True
        )
        raise typer.Exit(2)
    db = DB(resolved_db_path)
    uvicorn.run(create_app(db), host=resolved_host, port=resolved_port)
