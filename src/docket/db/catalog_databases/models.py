from typing import ClassVar

from sustained import Model
from sustained.schema import ColumnDef, String, Timestamp


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
