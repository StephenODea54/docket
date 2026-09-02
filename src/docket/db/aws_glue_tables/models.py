from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import (
    Boolean,
    ColumnDef,
    Integer,
    Json,
    String,
    Text,
    Timestamp,
)


class AwsGlueTableSelect(TypedDict):
    name: str | None
    database_name: str | None
    catalog_id: str | None
    description: str | None
    owner: str | None
    table_type: str | None
    created_by: str | None
    version_id: str | None
    retention: int | None
    is_registered_with_lake_formation: bool | None
    create_time: str | None
    update_time: str | None
    last_access_time: str | None
    last_analyzed_time: str | None
    view_original_text: str | None
    view_expanded_text: str | None
    parameters: str | None
    partition_keys: str | None
    storage_descriptor: str | None
    federated_table: str | None
    target_table: str | None
    lf_tags: str | None


class AwsGlueTableModel(Model):
    tableName: ClassVar[str] = "aws_glue_catalog_table"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "name": String(255),
        "database_name": String(255),
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
