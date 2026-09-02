from datetime import datetime
from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import ColumnDef, Index, Json, String, Timestamp


class CatalogJobExtractionSelect(TypedDict):
    id: str
    job_id: str
    cache_key: str
    model: str
    prompt_version: str
    extraction: str
    extracted_at: str | None


class CatalogJobExtractionInsert(TypedDict):
    job_id: str
    cache_key: str
    model: str
    prompt_version: str
    extraction: str
    extracted_at: datetime | str | None


class CatalogJobExtractionModel(Model):
    tableName: ClassVar[str] = "catalog_job_extractions"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "id": String(36, primary_key=True),
        "job_id": String(36, nullable=False, references="catalog_jobs.id"),
        "cache_key": String(128, nullable=False),
        "model": String(255, nullable=False),
        "prompt_version": String(16, nullable=False),
        "extraction": Json(nullable=False),
        "extracted_at": Timestamp(),
    }
    indexes: ClassVar[list[Index]] = [
        Index("uq_catalog_job_extractions_job_id", "job_id", unique=True)
    ]
