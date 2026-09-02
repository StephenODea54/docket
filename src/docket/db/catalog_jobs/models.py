from datetime import datetime
from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import ColumnDef, Index, Json, String, Timestamp


class CatalogJobSelect(TypedDict):
    id: str
    type: str
    name: str
    description: str | None
    role: str | None
    runtime: str | None
    last_modified: str | None
    attributes: str | None


class CatalogJobInsert(TypedDict):
    type: str
    name: str
    description: str | None
    role: str | None
    runtime: str | None
    last_modified: datetime | str | None
    attributes: str | None


class CatalogJobModel(Model):
    tableName: ClassVar[str] = "catalog_jobs"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "id": String(36, primary_key=True),
        "type": String(16, nullable=False),
        "name": String(255, nullable=False),
        "description": String(2048),
        "role": String(2048),
        "runtime": String(64),
        "last_modified": Timestamp(),
        "attributes": Json(),
    }
    indexes: ClassVar[list[Index]] = [
        Index("uq_catalog_jobs_type_name", "type", "name", unique=True)
    ]
