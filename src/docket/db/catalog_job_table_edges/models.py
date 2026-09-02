from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import Boolean, ColumnDef, Index, String, Text


class CatalogJobTableEdgeSelect(TypedDict):
    id: str
    job_id: str
    database_name: str | None
    table_name: str
    direction: str
    is_dynamic: bool
    evidence: str


class CatalogJobTableEdgeInsert(TypedDict):
    job_id: str
    database_name: str | None
    table_name: str
    direction: str
    is_dynamic: bool
    evidence: str


class CatalogJobTableEdgeModel(Model):
    tableName: ClassVar[str] = "catalog_job_table_edges"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "id": String(36, primary_key=True),
        "job_id": String(36, nullable=False, references="catalog_jobs.id"),
        "database_name": String(255),
        "table_name": String(255, nullable=False),
        "direction": String(8, nullable=False),
        "is_dynamic": Boolean(nullable=False),
        "evidence": Text(nullable=False),
    }
    indexes: ClassVar[list[Index]] = [
        Index("ix_catalog_job_table_edges_job_id", "job_id"),
        Index("ix_catalog_job_table_edges_table_name", "table_name"),
    ]
