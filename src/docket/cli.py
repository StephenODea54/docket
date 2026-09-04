import logging
from pathlib import Path

import typer
import uvicorn

from .config.env import env
from .db import DB
from .orchestrator import LlmEdgeExtractor
from .orchestrator import run as run_pipeline
from .web import create_app

app = typer.Typer(no_args_is_help=True)


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
