from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import ColumnDef, Json, String, Timestamp


class AwsCloudtrailLookupEventSelect(TypedDict):
    event_id: str | None
    event_name: str | None
    event_source: str | None
    event_time: str | None
    username: str | None
    region: str | None
    cloud_trail_event: str | None


class AwsCloudtrailLookupEventModel(Model):
    tableName: ClassVar[str] = "aws_cloudtrail_lookup_event"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "event_id": String(64),
        "event_name": String(255),
        "event_source": String(255),
        "event_time": Timestamp(),
        "username": String(255),
        "region": String(64),
        "cloud_trail_event": Json(),
        "start_time": Timestamp(),
        "end_time": Timestamp(),
    }
