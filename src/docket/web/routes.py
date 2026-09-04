from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..db.catalog_tables import CatalogTableModel
from ..db.utils import decode_column
from .diagrams import build_dag, build_erd

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
    """Render the table detail partial: metadata, columns, ERD, and DAG."""
    db = request.app.state.db
    table = db.clients["catalog_tables"].get_table(database_name, table_name)
    if table is None:
        return HTMLResponse("<p>Table not found.</p>", status_code=404)
    descriptor = decode_column(CatalogTableModel, table, "storage_descriptor") or {}
    partition_keys = decode_column(CatalogTableModel, table, "partition_keys") or []
    columns = descriptor.get("Columns") or []
    join_edges = db.clients["catalog_table_join_edges"].get_table_edges(table_name)
    edge_tables = {edge["left_table"] for edge in join_edges} | {
        edge["right_table"] for edge in join_edges
    }
    partner_names = sorted(edge_tables - {table_name})
    partners = db.clients["catalog_tables"].get_tables_by_names(partner_names)
    columns_by_table = {table_name: columns}
    for partner in partners:
        partner_descriptor = (
            decode_column(CatalogTableModel, partner, "storage_descriptor") or {}
        )
        columns_by_table.setdefault(
            partner["name"], partner_descriptor.get("Columns") or []
        )
    erd_source = build_erd(table_name, columns_by_table, join_edges)
    dag_source = build_dag(
        table_name,
        db.clients["catalog_job_table_edges"].get_table_edges,
        db.clients["catalog_job_table_edges"].get_job_edges,
        db.clients["catalog_jobs"].get_jobs_by_ids,
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/table_detail.html",
        {
            "table": table,
            "location": descriptor.get("Location"),
            "columns": columns,
            "partition_keys": partition_keys,
            "erd_source": erd_source,
            "dag_source": dag_source,
        },
    )
