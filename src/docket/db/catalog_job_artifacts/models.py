from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import ColumnDef, Index, String


class CatalogJobArtifactSelect(TypedDict):
    id: str
    job_id: str
    reference: str


class CatalogJobArtifactInsert(TypedDict):
    job_id: str
    reference: str


class CatalogJobArtifactModel(Model):
    tableName: ClassVar[str] = "catalog_job_artifacts"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "id": String(36, primary_key=True),
        "job_id": String(36, nullable=False, references="catalog_jobs.id"),
        "reference": String(2048, nullable=False),
    }
    indexes: ClassVar[list[Index]] = [
        Index(
            "uq_catalog_job_artifacts_job_id_reference",
            "job_id",
            "reference",
            unique=True,
        )
    ]
