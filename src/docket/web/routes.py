from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from ..db.catalog_tables import CatalogTableModel
from ..db.utils import decode_column
from .graph import build_dag, build_erd

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the full page with the database and table sidebar."""
    db = request.app.state.db
    databases = db.clients["catalog_databases"].get_databases()
    tables = db.clients["catalog_tables"].get_tables()
    tables_by_database: dict[str, list[str]] = {
        database["name"]: [] for database in databases
    }
    for table in tables:
        tables_by_database.setdefault(table["database_name"], []).append(table["name"])
    return request.app.state.templates.TemplateResponse(
        request, "index.html", {"tables_by_database": tables_by_database}
    )


@router.get("/tables/{database_name}/{table_name}", response_class=HTMLResponse)
async def table_detail(
    request: Request, database_name: str, table_name: str
) -> HTMLResponse:
    """Render the table detail partial: metadata, columns, and the join diagram."""
    db = request.app.state.db
    table = db.clients["catalog_tables"].get_table(database_name, table_name)
    if table is None:
        return HTMLResponse("<p>Table not found.</p>", status_code=404)
    descriptor = decode_column(CatalogTableModel, table, "storage_descriptor") or {}
    partition_keys = decode_column(CatalogTableModel, table, "partition_keys") or []
    job_edges = db.clients["catalog_job_table_edges"].get_table_edges([table_name])
    jobs = {
        job["id"]: f"{job['type']}: {job['name']}"
        for job in db.clients["catalog_jobs"].get_jobs_by_ids(
            sorted({edge["job_id"] for edge in job_edges})
        )
    }
    writers = sorted(
        {
            jobs[edge["job_id"]]
            for edge in job_edges
            if edge["direction"] == "write" and edge["job_id"] in jobs
        }
    )
    readers = sorted(
        {
            jobs[edge["job_id"]]
            for edge in job_edges
            if edge["direction"] == "read" and edge["job_id"] in jobs
        }
    )
    join_edges = db.clients["catalog_table_join_edges"].get_table_edges(table_name)
    graph = build_erd(
        database_name,
        table_name,
        table,
        join_edges,
        db.clients["catalog_tables"].get_tables_by_names,
        db.clients["catalog_jobs"].get_jobs_by_ids,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/table_detail.html",
        {
            "table": table,
            "location": descriptor.get("Location"),
            "columns": descriptor.get("Columns") or [],
            "partition_keys": partition_keys,
            "graph": graph,
            "writers": writers,
            "readers": readers,
        },
    )


@router.get("/dag/{database_name}/{table_name}", response_class=HTMLResponse)
async def dag(
    request: Request,
    database_name: str,
    table_name: str,
    depth: int = Query(default=2),
) -> HTMLResponse:
    """Render the lineage diagram partial for a table."""
    db = request.app.state.db
    table = db.clients["catalog_tables"].get_table(database_name, table_name)
    if table is None:
        return HTMLResponse("<p>Table not found.</p>", status_code=404)
    depth = max(1, min(depth, 4))
    graph = build_dag(
        database_name,
        table_name,
        db.clients["catalog_job_table_edges"].get_table_edges,
        db.clients["catalog_job_table_edges"].get_job_edges,
        db.clients["catalog_jobs"].get_jobs_by_ids,
        db.clients["catalog_tables"].get_tables_by_names,
        depth,
    )
    return request.app.state.templates.TemplateResponse(
        request, "partials/dag.html", {"table": table, "depth": depth, "graph": graph}
    )
