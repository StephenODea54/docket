from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import ColumnDef, Integer, String, Text, Timestamp


class AwsS3ObjectSelect(TypedDict):
    bucket_name: str | None
    key: str | None
    prefix: str | None
    size: int | None
    etag: str | None
    content_type: str | None
    last_modified: str | None
    body: str | None


class AwsS3ObjectModel(Model):
    tableName: ClassVar[str] = "aws_s3_object"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "bucket_name": String(255),
        "key": String(2048),
        "prefix": String(2048),
        "size": Integer(),
        "etag": String(128),
        "content_type": String(255),
        "last_modified": Timestamp(),
        "body": Text(),
    }
