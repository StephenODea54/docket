from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import ColumnDef, Index, String, Text


class CatalogTableJoinEdgeSelect(TypedDict):
    id: str
    job_id: str
    left_database: str | None
    left_table: str
    left_column: str
    right_database: str | None
    right_table: str
    right_column: str
    evidence: str


class CatalogTableJoinEdgeInsert(TypedDict):
    job_id: str
    left_database: str | None
    left_table: str
    left_column: str
    right_database: str | None
    right_table: str
    right_column: str
    evidence: str


class CatalogTableJoinEdgeModel(Model):
    tableName: ClassVar[str] = "catalog_table_join_edges"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "id": String(36, primary_key=True),
        "job_id": String(36, nullable=False, references="catalog_jobs.id"),
        "left_database": String(255),
        "left_table": String(255, nullable=False),
        "left_column": String(255, nullable=False),
        "right_database": String(255),
        "right_table": String(255, nullable=False),
        "right_column": String(255, nullable=False),
        "evidence": Text(nullable=False),
    }
    indexes: ClassVar[list[Index]] = [
        Index("ix_catalog_table_join_edges_job_id", "job_id"),
        Index("ix_catalog_table_join_edges_left_table", "left_table"),
        Index("ix_catalog_table_join_edges_right_table", "right_table"),
    ]
