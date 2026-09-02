from datetime import datetime
from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import ColumnDef, String, Timestamp


class CatalogDatabaseSelect(TypedDict):
    id: str
    name: str
    arn: str | None
    catalog_id: str | None
    description: str | None
    location_uri: str | None
    create_time: str | None


class CatalogDatabaseInsert(TypedDict):
    name: str
    arn: str | None
    catalog_id: str | None
    description: str | None
    location_uri: str | None
    create_time: datetime | str | None


class CatalogDatabaseModel(Model):
    tableName: ClassVar[str] = "catalog_databases"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "id": String(36, primary_key=True),
        "name": String(255, unique=True, nullable=False),
        "arn": String(2048),
        "catalog_id": String(64),
        "description": String(2048),
        "location_uri": String(2048),
        "create_time": Timestamp(),
    }
