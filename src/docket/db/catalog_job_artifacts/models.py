from datetime import datetime
from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import ColumnDef, Index, String, Timestamp


class CatalogJobArtifactSelect(TypedDict):
    id: str
    job_id: str
    location: str
    cache_key: str
    last_modified: str | None


class CatalogJobArtifactInsert(TypedDict):
    job_id: str
    location: str
    cache_key: str
    last_modified: datetime | str | None


class CatalogJobArtifactModel(Model):
    tableName: ClassVar[str] = "catalog_job_artifacts"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "id": String(36, primary_key=True),
        "job_id": String(36, nullable=False, references="catalog_jobs.id"),
        "location": String(2048, nullable=False),
        "cache_key": String(128, nullable=False),
        "last_modified": Timestamp(),
    }
    indexes: ClassVar[list[Index]] = [
        Index(
            "uq_catalog_job_artifacts_job_id_location",
            "job_id",
            "location",
            unique=True,
        )
    ]
