from datetime import datetime
from typing import ClassVar, TypedDict

from sustained import Model
from sustained.schema import Boolean, ColumnDef, Index, String, Timestamp


class CatalogAuditEventSelect(TypedDict):
    id: str
    event_id: str
    database_name: str | None
    table_name: str
    event_name: str
    event_time: str | None
    username: str | None
    region: str | None
    flagged: bool
    reported_at: str | None


class CatalogAuditEventInsert(TypedDict):
    event_id: str
    database_name: str | None
    table_name: str
    event_name: str
    event_time: datetime | str | None
    username: str | None
    region: str | None
    flagged: bool


class CatalogAuditEventModel(Model):
    tableName: ClassVar[str] = "catalog_audit_events"
    tableColumns: ClassVar[dict[str, ColumnDef]] = {
        "id": String(36, primary_key=True),
        "event_id": String(64, nullable=False),
        "database_name": String(255),
        "table_name": String(255, nullable=False),
        "event_name": String(64, nullable=False),
        "event_time": Timestamp(),
        "username": String(255),
        "region": String(64),
        "flagged": Boolean(nullable=False),
        "reported_at": Timestamp(nullable=False),
    }
    indexes: ClassVar[list[Index]] = [
        Index(
            "uq_catalog_audit_events_event_id_table_name",
            "event_id",
            "table_name",
            unique=True,
        )
    ]
