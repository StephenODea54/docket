import logging
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
import uvicorn

from .audit import find_flagged_deletions, parse_deletion_events
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
def audit(
    hours: int = 24,
    show_all: bool = typer.Option(
        False, "--all", help="Re-report deletions that were already reported."
    ),
    db_path: str | None = None,
) -> None:
    """Audit recent Glue table deletions against the catalog's dependency edges."""
    db, resolved = _open_db(db_path)
    typer.echo(_catalog_age(resolved))
    start = datetime.now(UTC) - timedelta(hours=hours)
    cloudtrail = db.clients["aws_cloudtrail_events"]
    try:
        rows = cloudtrail.get_events("DeleteTable", start) + cloudtrail.get_events(
            "BatchDeleteTable", start
        )
    except sqlite3.OperationalError as error:
        typer.echo(
            f"cloudtrail query failed (check AWS credentials): {error}", err=True
        )
        raise typer.Exit(2) from error
    events = parse_deletion_events(rows)
    seen = db.clients["catalog_audit_events"].get_event_ids(
        sorted({event["event_id"] for event in events})
    )
    new_events = [event for event in events if event["event_id"] not in seen]
    to_report = events if show_all else new_events
    findings = find_flagged_deletions(
        to_report,
        lambda database, table: _collect_dependents(db, database or "", table),
    )
    for finding in findings:
        event = finding["event"]
        table = (
            f"{event['database']}.{event['table']}"
            if event["database"]
            else event["table"]
        )
        typer.echo(
            f"DELETED WITH DEPENDENTS: {table} ({event['event_name']} by "
            f"{event['username'] or 'unknown'} at {event['event_time'] or 'unknown'}, "
            f"{event['region'] or 'unknown'})",
            err=True,
        )
        typer.echo(format_report(finding["report"]), err=True)
        typer.echo("", err=True)
    if new_events:
        flagged = {
            (finding["event"]["event_id"], finding["event"]["table"])
            for finding in findings
        }
        records = {
            (event["event_id"], event["table"]): {
                "event_id": event["event_id"],
                "database_name": event["database"],
                "table_name": event["table"],
                "event_name": event["event_name"],
                "event_time": event["event_time"],
                "username": event["username"],
                "region": event["region"],
                "flagged": (event["event_id"], event["table"]) in flagged,
            }
            for event in new_events
        }
        with db.transaction():
            db.clients["catalog_audit_events"].insert_events(list(records.values()))
    label = "" if show_all else "new "
    typer.echo(f"{len(to_report)} {label}glue deletion(s) in the last {hours}h")
    if findings:
        raise typer.Exit(1)
    typer.echo("none had dependents")


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
