from typing import ClassVar

from sustained import Model
from sustained.schema import (
    Boolean,
    ColumnDef,
    Index,
    Integer,
    Json,
    String,
    Text,
    Timestamp,
)


class CatalogTableModel(Model):
    tableName: ClassVar[str] = "catalog_tables"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "id": String(36, primary_key=True),
        "database_id": String(36, nullable=False, references="catalog_databases.id"),
        "name": String(255, nullable=False),
        "catalog_id": String(64),
        "description": String(2048),
        "owner": String(255),
        "table_type": String(64),
        "created_by": String(2048),
        "version_id": String(64),
        "retention": Integer(),
        "is_registered_with_lake_formation": Boolean(),
        "create_time": Timestamp(),
        "update_time": Timestamp(),
        "last_access_time": Timestamp(),
        "last_analyzed_time": Timestamp(),
        "view_original_text": Text(),
        "view_expanded_text": Text(),
        "parameters": Json(),
        "partition_keys": Json(),
        "storage_descriptor": Json(),
        "federated_table": Json(),
        "target_table": Json(),
        "lf_tags": Json(),
    }
    indexes: ClassVar[list[Index]] = [
        Index("uq_catalog_tables_database_id_name", "database_id", "name", unique=True)
    ]
