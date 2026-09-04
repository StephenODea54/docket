import logging

import typer

from .db import DB
from .orchestrator import LlmEdgeExtractor
from .orchestrator import run as run_pipeline

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
