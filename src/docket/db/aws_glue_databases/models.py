from typing import ClassVar

from sustained import Model
from sustained.schema import ColumnDef, String, Timestamp


class AwsGlueDatabaseModel(Model):
    tableName: ClassVar[str] = "aws_glue_catalog_database"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "name": String(255),
        "arn": String(2048),
        "catalog_id": String(64),
        "description": String(2048),
        "location_uri": String(2048),
        "create_time": Timestamp(),
    }
